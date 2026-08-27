#!/usr/bin/env python3
"""ticket-driver bot CLI: fetch nouveaux retours + report/mark sur GitLab, GitHub, Redmine."""
import argparse, json, mimetypes, os, re, subprocess, sys, urllib.parse
from datetime import datetime, timedelta, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
STATE_DIR = os.path.join(SKILL_DIR, "state")
DEFAULT_CONFIG = os.path.join(STATE_DIR, "config.json")
DEFAULT_STATE = os.path.join(STATE_DIR, "projects.json")

# identités (utilisées pour ne jamais traiter nos propres retours)
ME_GITLAB = "princesandjong777"
ME_GITHUB = "Blue-B-code"
ME_REDMINE = "Paul Sandjong"

# --- helpers shell -----------------------------------------------------------
def sh(cmd, check=True, strip=True):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError("cmd échoué: %s\n%s" % (" ".join(cmd), r.stderr.strip()))
    return r.stdout.strip() if strip else r.stdout

def json_from(cmd):
    out = sh(cmd)
    return json.loads(out) if out.strip() else []

# --- clients API -------------------------------------------------------------
def glab_api(project_id, path, method="GET", fields=None):
    cmd = ["glab", "api", "projects/%s/%s" % (project_id, path)]
    if method == "POST":
        cmd = ["glab", "api", "--method", "POST", "projects/%s/%s" % (project_id, path)]
    elif method == "PUT":
        cmd = ["glab", "api", "--method", "PUT", "projects/%s/%s" % (project_id, path)]
    if fields:
        for k, v in fields.items():
            cmd += ["-f", "%s=%s" % (k, v)]
    out = sh(cmd)
    return json.loads(out) if out.strip() else {}

def gh_api(owner_repo, path, method="GET", data=None):
    cmd = ["gh", "api", "--method", method, "repos/%s/%s" % (owner_repo, path)]
    if data:
        cmd += ["-f", "body=%s" % data]
    out = sh(cmd)
    return json.loads(out) if out.strip() else {}

def redmine(base, key, path, method="GET", payload=None):
    url = "%s/%s" % (base.rstrip("/"), path.lstrip("/"))
    cmd = ["curl", "-sS", "-m", "30", "-H", "X-Redmine-API-Key: %s" % key]
    if method == "PUT":
        cmd += ["-X", "PUT", "-H", "Content-Type: application/json", "--data", json.dumps(payload)]
    cmd += [url]
    out = sh(cmd)
    return json.loads(out) if out.strip() else {}

def redmine_upload(base, key, filepath):
    # Redmine uploads.json accepts the raw file body + a filename via Content-Disposition.
    url = "%s/uploads.json" % base.rstrip("/")
    filename = os.path.basename(filepath)
    cmd = [
        "curl", "-sS", "-m", "60",
        "-H", "X-Redmine-API-Key: %s" % key,
        "-H", "Content-Type: application/octet-stream",
        "-H", "Content-Disposition: attachment; filename=%s" % filename,
        "--data-binary", "@%s" % filepath,
        url,
    ]
    out = sh(cmd)
    return json.loads(out).get("upload", {})

def redmine_lookup(base, key, project_id):
    # Builds name->id maps for statuses and assignees from issues of a Redmine project.
    url = "%s/issues.json?project_id=%s&status_id=*&limit=100" % (base.rstrip("/"), project_id)
    cmd = ["curl", "-sS", "-m", "30", "-H", "X-Redmine-API-Key: %s" % key, url]
    out = sh(cmd)
    data = json.loads(out) if out.strip() else {}
    statuses, assignees = {}, {}
    for i in data.get("issues", []):
        st = i.get("status")
        if st:
            statuses[st["name"]] = st["id"]
        a = i.get("assigned_to")
        if a:
            assignees[a["name"]] = a["id"]
    return statuses, assignees

# --- état --------------------------------------------------------------------
def load_config(path):
    with open(path) as f:
        return json.load(f)

def load_state(state_path):
    if os.path.exists(state_path):
        with open(state_path) as f:
            return json.load(f)
    return {}

def save_state(state_path, state):
    with open(state_path, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)

def ensure_slot(state, project, key, sub):
    state.setdefault(project, {}).setdefault(key, {}).setdefault(sub, [])

# --- extraction ticket_ids depuis une MR -------------------------------------
def ticket_ids_from_mr(mr):
    hay = " ".join([
        mr.get("source_branch") or "",
        mr.get("target_branch") or "",
        mr.get("title") or "",
        (mr.get("description") or "")[:2000],
    ])
    ids = set()
    for m in re.finditer(r"[-\s#/](?:feature[-_]?)?(\d{4,})", hay):
        ids.add(int(m.group(1)))
    return sorted(ids)

# --- fetch -------------------------------------------------------------------
def _current_sprint_id(redmine_cfg):
    """Version du sprint courant = DH-OpenIMIS<AAA><MM><NN> ouverte avec due_date la plus proche >= aujourd'hui."""
    if not redmine_cfg:
        return None
    scan = redmine_cfg.get("sprint_scan_project_id")
    prefix = redmine_cfg.get("sprint_prefix", "DH-OpenIMIS")
    if not scan:
        return None
    try:
        data = redmine(redmine_cfg["base_url"], redmine_cfg["api_key"], "projects/%d/versions.json?limit=100" % scan)
    except Exception:
        return None
    today = datetime.now(timezone.utc).date()
    best = None
    for v in data.get("versions", []):
        n = v.get("name", "")
        if not n.startswith(prefix) or not n[len(prefix):].isdigit():
            continue
        due = v.get("due_date")
        if not due or v.get("status") == "closed":
            continue
        try:
            dd = datetime.strptime(due, "%Y-%m-%d").date()
        except Exception:
            continue
        if dd >= today and (best is None or dd < best[0]):
            best = (dd, v["id"])
    return best[1] if best else None


def fetch_project(proj, name, state, redmine_cfg):
    items = []
    me = proj.get("me", ME_GITLAB)
    host = proj.get("host", "gitlab")

    # --- GitLab: MR ouvertes + discussions ---
    if host == "gitlab":
        pid = proj["project_id"]
        mrs = json_from(["glab", "api", "projects/%d/merge_requests?state=opened&author_username=%s&per_page=100" % (pid, me)])
        mrs = [m for m in mrs if (m.get("author") or {}).get("username") == me]
        for mr in mrs:
            iid = mr["iid"]
            key = "gitlab_mr_%s" % iid
            processed = set(state.get(name, {}).get(key, {}).get("processed_notes", []))
            disc = json_from(["glab", "api", "projects/%d/merge_requests/%d/discussions" % (pid, iid)])
            for d in disc:
                did = d.get("id")
                for note in d.get("notes", []):
                    nid = note.get("id")
                    if not nid or nid in processed:
                        continue
                    if note.get("system"):
                        continue
                    if (note.get("author") or {}).get("username") == me:
                        continue
                    body = (note.get("body") or "").strip()
                    if not body:
                        continue
                    items.append({
                        "kind": "mr_comment", "project": name,
                        "mr_iid": iid, "note_id": nid, "discussion_id": did,
                        "author": (note.get("author") or {}).get("username"),
                        "body": body,
                        "resolvable": bool(note.get("resolvable")),
                        "title": mr.get("title", ""),
                        "url": mr.get("web_url", ""),
                        "key": key, "sub": "processed_notes", "sub_id": nid,
                    })
        my_tickets = set()
        for mr in mrs:
            for t in ticket_ids_from_mr(mr):
                my_tickets.add(t)
        # Retours Redmine récents (24h) du projet associé, pour couvrir le feedback ticket
        rp = (proj.get("redmine") or {}).get("project_id")
        if rp and redmine_cfg:
            window = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
            try:
                iss = redmine(redmine_cfg["base_url"], redmine_cfg["api_key"],
                              "issues.json?project_id=%d&updated_on=%%3E%s&limit=50" % (rp, window))
                for issue in iss.get("issues", []):
                    tid = issue.get("id")
                    if tid not in my_tickets:
                        continue
                    key = "redmine_%d" % tid
                    processed_j = set(state.get(name, {}).get(key, {}).get("processed_journals", []))
                    data = redmine(redmine_cfg["base_url"], redmine_cfg["api_key"],
                                   "issues/%d.json?include=journals" % tid)
                    for j in (data.get("issue", {}).get("journals") or []):
                        jid = j.get("id")
                        notes = (j.get("notes") or "").strip()
                        if not jid or jid in processed_j or not notes:
                            continue
                        if (j.get("user") or {}).get("name") == redmine_cfg.get("me", ME_REDMINE):
                            continue
                        items.append({
                            "kind": "ticket_journal", "project": name,
                            "ticket": tid, "journal_id": jid,
                            "author": (j.get("user") or {}).get("name"),
                            "body": notes, "created_on": j.get("created_on"),
                            "url": "%s/issues/%d" % (redmine_cfg["base_url"].rstrip("/"), tid),
                            "key": key, "sub": "processed_journals", "sub_id": jid,
                        })
            except Exception:
                pass
    # --- GitHub: PR ouvertes + comments (placeholder pour phase suivante) ---
    elif host == "github":
        # repo attendu au format owner/name
        rr = proj.get("project_path")
        prs = gh_api(rr, "pulls?state=open&per_page=100")
        prs = [pr for pr in prs if (pr.get("user") or {}).get("login") == me]
        for pr in prs:
            iid = pr["number"]
            key = "github_pr_%s" % iid
            processed = set(state.get(name, {}).get(key, {}).get("processed_comments", []))
            comments = gh_api(rr, "pulls/%d/comments?per_page=100" % iid)
            for c in comments:
                cid = c.get("id")
                if not cid or cid in processed:
                    continue
                if (c.get("user") or {}).get("login") == me:
                    continue
                body = (c.get("body") or "").strip()
                if not body:
                    continue
                items.append({
                    "kind": "pr_comment", "project": name,
                    "pr_number": iid, "comment_id": cid,
                    "author": (c.get("user") or {}).get("login"),
                    "body": body,
                    "url": c.get("html_url", ""),
                    "key": key, "sub": "processed_comments", "sub_id": cid,
                })
    # --- Tickets du sprint courant assignés à moi (source complémentaire) ---
    routes = (redmine_cfg or {}).get("sprint_routes", {})
    rpids_for_this = [int(k) for k, v in routes.items() if v == name]
    if rpids_for_this and redmine_cfg:
        sprint_id = _current_sprint_id(redmine_cfg)
        if sprint_id:
            me_id = redmine_cfg.get("me_id", 976)
            try:
                iss = redmine(redmine_cfg["base_url"], redmine_cfg["api_key"],
                              "issues.json?assigned_to_id=%d&fixed_version_id=%d&status_id=open&limit=100" % (me_id, sprint_id))
                for issue in iss.get("issues", []):
                    rp = (issue.get("project") or {}).get("id")
                    if rp not in rpids_for_this:
                        continue
                    tid = issue.get("id")
                    items.append({
                        "kind": "sprint_ticket", "project": name,
                        "ticket_id": tid, "subject": issue.get("subject", ""),
                        "body": (issue.get("description") or ""),
                        "tracker": (issue.get("tracker") or {}).get("name"),
                        "redmine_project_id": rp,
                        "url": "%s/issues/%d" % (redmine_cfg["base_url"].rstrip("/"), tid),
                        "key": "sprint_ticket_%d" % tid, "sub": "processed_tickets", "sub_id": tid,
                    })
            except Exception:
                pass
    return items

# --- commandes -----------------------------------------------------------------
def cmd_fetch(args, cfg, state):
    proj = cfg["projects"][args.project]
    items = fetch_project(proj, args.project, state, cfg.get("redmine", {}))
    summary = {"project": args.project, "host": proj.get("host"), "count": len(items), "items": items}
    if args.out:
        with open(args.out, "w") as f:
            json.dump(summary, f, indent=2)
    if args.pretty:
        print(json.dumps(summary, indent=2))
        if not items:
            print("Aucun nouveau retour pour %s." % args.project)
    else:
        print("%d" % len(items))
    return summary

def cmd_mark(args, cfg, state):
    with open(args.file) as f:
        summary = json.load(f)
    project = summary["project"]
    for item in summary.get("items", []):
        ensure_slot(state, project, item["key"], item["sub"])
        if item["sub_id"] not in state[project][item["key"]][item["sub"]]:
            state[project][item["key"]][item["sub"]].append(item["sub_id"])
    save_state(args.state_path, state)
    print("marqués: %d" % len(summary.get("items", [])))

def cmd_mark_key(args, cfg, state):
    ensure_slot(state, args.project, args.key, args.sub)
    if args.id not in state[args.project][args.key][args.sub]:
        state[args.project][args.key][args.sub].append(args.id)
    save_state(args.state_path, state)
    print("marqué: %s %s %s" % (args.project, args.key, args.id))

def cmd_report(args, cfg):
    proj = cfg["projects"][args.project]
    host = proj.get("host")
    target, _, target_id = args.target.partition(":")
    text = args.text or ""
    dry = args.dry_run

    def do(desc, fn):
        if dry:
            print("[DRY-RUN] %s" % desc)
            return None
        return fn()

    if host == "gitlab" and target == "mr":
        pid = proj["project_id"]
        iid = int(target_id)
        if args.action == "reply":
            return do("reply MR %s discussion %s: %s" % (iid, args.discussion_id, text[:80]),
                      lambda: glab_api(pid, "merge_requests/%d/discussions/%s/notes" % (iid, args.discussion_id), "POST", {"body": text}))
        if args.action == "resolve":
            return do("resolve MR %s discussion %s" % (iid, args.discussion_id),
                      lambda: glab_api(pid, "merge_requests/%d/discussions/%s" % (iid, args.discussion_id), "PUT", {"resolved": "true"}))
        if args.action == "summary":
            return do("summary MR %s: %s" % (iid, text[:80]),
                      lambda: glab_api(pid, "merge_requests/%d/notes" % iid, "POST", {"body": text}))
    elif host == "github" and target == "pr":
        rr = proj["project_path"]
        num = int(target_id)
        if args.action == "reply" and args.comment_id:
            return do("reply PR %s comment %s: %s" % (num, args.comment_id, text[:80]),
                      lambda: gh_api(rr, "pulls/comments/%s/replies" % args.comment_id, "POST", text))
        if args.action == "summary":
            return do("summary PR %s: %s" % (num, text[:80]),
                      lambda: gh_api(rr, "issues/%d/comments" % num, "POST", text))
    elif target == "ticket":
        rm = cfg["redmine"]
        tid = int(target_id)
        if args.action == "journal":
            issue = {"notes": text}
            if args.status_id is not None:
                issue["status_id"] = args.status_id
            elif args.status_name:
                st, _ = redmine_lookup(rm["base_url"], rm["api_key"], rm.get("project_id", 199))
                if args.status_name in st:
                    issue["status_id"] = st[args.status_name]
            if args.assignee_id is not None:
                issue["assigned_to_id"] = args.assignee_id
            elif args.assignee_name:
                _, a = redmine_lookup(rm["base_url"], rm["api_key"], rm.get("project_id", 199))
                if args.assignee_name in a:
                    issue["assigned_to_id"] = a[args.assignee_name]
            if args.attach:
                up = redmine_upload(rm["base_url"], rm["api_key"], args.attach)
                if up.get("token"):
                    issue["uploads"] = [{"token": up["token"], "filename": os.path.basename(args.attach), "content_type": "application/octet-stream"}]
            return do("journal Redmine %s (recette)" % tid,
                      lambda: redmine(rm["base_url"], rm["api_key"], "issues/%d.json" % tid, "PUT", {"issue": issue}))
    raise SystemExit("report non supporté: host=%s target=%s action=%s" % (host, target, args.action))

def cmd_set_mode(args, cfg):
    proj = cfg["projects"].get(args.project)
    if not proj:
        raise SystemExit("projet inconnu: %s (disponibles: %s)" % (args.project, ", ".join(cfg["projects"])))
    if args.mode not in ("auto", "propose", "signal"):
        raise SystemExit("mode invalide: %s (auto|propose|signal)" % args.mode)
    proj["mode"] = args.mode
    with open(args.config, "w") as f:
        json.dump(cfg, f, indent=2, sort_keys=True)
    print("mode %s -> %s" % (args.project, args.mode))

def cmd_modes(args, cfg):
    print("mode par projet :")
    for name, proj in cfg["projects"].items():
        print("  %-12s %s" % (name, proj.get("mode", "propose")))

def main():
    ap = argparse.ArgumentParser(prog="rfbot", description="ticket-driver bot")
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--state-path", default=DEFAULT_STATE)
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="lister les nouveaux retours")
    f.add_argument("--project", required=True); f.add_argument("--out", default=None); f.add_argument("--pretty", action="store_true")
    f.set_defaults(func=cmd_fetch)

    m = sub.add_parser("mark", help="marquer des items comme traités")
    m.add_argument("--file", required=True)
    m.set_defaults(func=cmd_mark)

    mk = sub.add_parser("mark-key", help="marquer un seul item (key/sub/id)")
    mk.add_argument("--project", required=True); mk.add_argument("--key", required=True)
    mk.add_argument("--sub", required=True); mk.add_argument("--id", type=int, required=True)
    mk.set_defaults(func=cmd_mark_key)

    r = sub.add_parser("report", help="poster une action (reply/resolve/summary/journal)")
    r.add_argument("--project", required=True)
    r.add_argument("--target", required=True, help="mr:33 | pr:12 | ticket:37862")
    r.add_argument("--action", required=True, help="reply|resolve|summary|journal")
    r.add_argument("--text", default="")
    r.add_argument("--discussion-id", default=""); r.add_argument("--comment-id", default="")
    r.add_argument("--status", dest="status_id", type=int, default=None)
    r.add_argument("--status-name", default=None)
    r.add_argument("--assignee", dest="assignee_id", type=int, default=None)
    r.add_argument("--assignee-name", default=None)
    r.add_argument("--attach", default=None)
    r.add_argument("--dry-run", action="store_true")
    r.set_defaults(func=cmd_report)

    sm = sub.add_parser("set-mode", help="changer le mode d'un projet (auto|propose|signal)")
    sm.add_argument("--project", required=True); sm.add_argument("--mode", required=True)
    sm.set_defaults(func=cmd_set_mode)

    mo = sub.add_parser("modes", help="lister les modes des projets")
    mo.set_defaults(func=cmd_modes)

    args = ap.parse_args()
    cfg = load_config(args.config)
    if args.cmd in ("set-mode", "modes"):
        args.func(args, cfg)
    else:
        state = load_state(args.state_path)
        args.func(args, cfg, state) if args.cmd != "report" else args.func(args, cfg)

if __name__ == "__main__":
    main()
