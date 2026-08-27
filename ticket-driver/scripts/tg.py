#!/usr/bin/env python3
"""Telegram helper pour ticket-driver : envoi d'approbation à boutons, info, et poll des callbacks."""
import argparse, json, os, subprocess, sys, time, urllib.parse, urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
STATE_DIR = os.path.join(SKILL_DIR, "state")
CONFIG = os.path.join(STATE_DIR, "config.json")
APPROVE_SH = os.path.join(SCRIPT_DIR, "ticket-driver-approve.sh")
OFFSET_FILE = os.path.join(STATE_DIR, "tg_offset.txt")

def load_cfg():
    with open(CONFIG) as f:
        return json.load(f)

def ensure_creds(cfg):
    tg = cfg.get("telegram", {})
    if not tg.get("bot_token"):
        raise SystemExit("telegram.bot_token non configuré (à renseigner dans state/config.json)")
    if not tg.get("chat_id"):
        raise SystemExit("telegram.chat_id non configuré (à renseigner dans state/config.json)")
    return tg

def api(cfg, method, params=None):
    token = cfg["telegram"]["bot_token"]
    url = "https://api.telegram.org/bot%s/%s" % (token, method)
    data = urllib.parse.urlencode(params or {}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode())

_SEV_EMOJI = {"bloquante": "⛔", "élevée": "🔴", "elevee": "🔴", "moyenne": "🟠", "basse": "🟡", "info": "ℹ️"}

def send_approval(project, mr, title, url, summary, severity):
    cfg = load_cfg()
    tg = ensure_creds(cfg)
    sev = (severity or "n/a").lower()
    emoji = _SEV_EMOJI.get(sev, "🔎")
    text = (
        "%s Revue à valider — %s (MR !%s)\n\n"
        "**%s**\n%s\n\n%s\n\n"
        "👉 Approuve pour que je corrige + pousse + reporte, ou rejette."
        % (emoji, project, mr, title, url, (summary or "—")[:3400])
    )
    keyboard = {"inline_keyboard": [[
        {"text": "✅ Approuver", "callback_data": "review_fix|%s|%s|approve" % (project, mr)},
        {"text": "❌ Rejeter", "callback_data": "review_fix|%s|%s|reject" % (project, mr)},
    ]]}
    res = api(cfg, "sendMessage", {"chat_id": tg["chat_id"], "text": text,
                                   "reply_markup": json.dumps(keyboard)})
    print("message_id:", res["result"]["message_id"])

def send_info(project, text):
    cfg = load_cfg()
    tg = ensure_creds(cfg)
    res = api(cfg, "sendMessage", {"chat_id": tg["chat_id"], "text": text})
    print("message_id:", res["result"]["message_id"])

def update_approvals(project, key, status, proposal=None):
    path = os.path.join(STATE_DIR, "approvals.json")
    state = {}
    if os.path.exists(path):
        with open(path) as f:
            state = json.load(f)
    k = "%s:%s" % (project, key)
    state[k] = {"status": status}
    if proposal:
        state[k]["proposal"] = proposal
    with open(path, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)

def load_offset():
    if os.path.exists(OFFSET_FILE):
        with open(OFFSET_FILE) as f:
            return int(f.read().strip())
    return 0

def save_offset(off):
    with open(OFFSET_FILE, "w") as f:
        f.write(str(off))

def _status(project, key):
    path = os.path.join(STATE_DIR, "approvals.json")
    st = {}
    if os.path.exists(path):
        with open(path) as f: st = json.load(f)
    return (st.get("%s:%s" % (project, key)) or {}).get("status")

def _replace_buttons(cfg, cq, label):
    """Remplace les boutons par un libellé non interactif (désactive tout second clic)."""
    msg = cq.get("message", {})
    cid, mid = msg.get("chat", {}).get("id"), msg.get("message_id")
    if not cid or not mid:
        return
    text = (msg.get("text") or "") + "\n\n" + label
    try:
        api(cfg, "editMessageText", {"chat_id": cid, "message_id": mid, "text": text,
                                     "reply_markup": json.dumps({"inline_keyboard": []})})
    except Exception as e:
        print("editMessageText error:", e, file=sys.stderr)

def handle_callback(cfg, cq):
    data = cq.get("data", "") or ""
    parts = data.split("|")
    if len(parts) != 4 or parts[0] != "review_fix":
        print("callback inconnu:", data)
        return
    _, project, mr, action = parts
    key = "gitlab_mr_%s" % mr
    # Ticket sprint ? La proposition porte MARK_KEY: sprint_ticket_*
    prop = os.path.join(STATE_DIR, "proposals", "%s_%s.md" % (project, mr))
    if os.path.exists(prop):
        try:
            with open(prop) as f:
                content = f.read()
            if "MARK_KEY: sprint_ticket_" in content:
                key = "sprint_ticket_%s" % mr
        except Exception:
            pass
    # 1) accuser réception (arrête le spinner du bouton)
    try:
        api(cfg, "answerCallbackQuery", {"callback_query_id": cq["id"], "text": "ok"})
    except Exception as e:
        print("answerCallbackQuery error:", e, file=sys.stderr)
    status = _status(project, key)
    # déjà décidé / en cours → pas de double traitement
    if status in ("approved", "rejected", "processing"):
        label = "Déjà traité" if status in ("approved", "rejected") else "⏳ Traitement en cours…"
        _replace_buttons(cfg, cq, label)
        return
    if action == "approve":
        print("APPROVE %s !%s -> approve.sh" % (project, mr))
        update_approvals(project, key, "processing")
        _replace_buttons(cfg, cq, "⏳ Traitement en cours…")
        rc = subprocess.run(["bash", APPROVE_SH, project, mr], check=False).returncode
        _replace_buttons(cfg, cq, "✅ Traitement terminé" if rc == 0 else "❌ Échec du traitement (voir logs)")
    elif action == "reject":
        print("REJECT %s !%s" % (project, mr))
        update_approvals(project, key, "rejected")
        _replace_buttons(cfg, cq, "❌ Rejeté")

def cmd_poll(args):
    cfg = load_cfg()
    ensure_creds(cfg)
    offset = load_offset()
    while True:
        try:
            res = api(cfg, "getUpdates", {"timeout": 0, "offset": offset})
        except Exception as e:
            print("getUpdates error:", e, file=sys.stderr)
            if args.once:
                break
            time.sleep(cfg.get("telegram", {}).get("poll_interval", 3))
            continue
        for u in res.get("result", []):
            offset = u["update_id"] + 1
            cq = u.get("callback_query")
            if cq:
                handle_callback(cfg, cq)
                save_offset(offset)
        if args.once:
            break
        time.sleep(cfg.get("telegram", {}).get("poll_interval", 3))

def main():
    ap = argparse.ArgumentParser(prog="tg", description="ticket-driver telegram")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("send-approval")
    a.add_argument("--project", required=True)
    a.add_argument("--mr", required=True)
    a.add_argument("--title", default="")
    a.add_argument("--url", default="")
    a.add_argument("--summary", default="")
    a.add_argument("--severity", default="")
    a.set_defaults(func=lambda args: send_approval(args.project, args.mr, args.title, args.url, args.summary, args.severity))

    i = sub.add_parser("send-info")
    i.add_argument("--project", required=True)
    i.add_argument("--text", required=True)
    i.set_defaults(func=lambda args: send_info(args.project, args.text))

    p = sub.add_parser("poll")
    p.add_argument("--once", action="store_true")
    p.set_defaults(func=cmd_poll)

    args = ap.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
