#!/bin/bash
# ticket-driver cron wrapper — route selon le mode :
#   auto    : corriger + push + report (codex exec)
#   propose : le MODÈLE fait un résumé concis du fix, envoie l'approbation Telegram (✅/❌), ne pousse pas
#   signal  : notifier uniquement
# Verrou par projet (state/locks/<projet>) pour éviter les runs concurrents (codex exec long).
# RFBOT_DRY=1 => logge sans agir (test).
set -euo pipefail
SKILL_DIR="$HOME/.codex-local/skills/ticket-driver"
CONFIG="$SKILL_DIR/state/config.json"
RFBOT="$SKILL_DIR/scripts/rfbot.py"
TG="$SKILL_DIR/scripts/tg.py"
LOGDIR="$SKILL_DIR/state/logs"
PROPOSALS="$SKILL_DIR/state/proposals"
LOCK_DIR="$SKILL_DIR/state/locks"
CODEX=/home/y-note/bin/codex
mkdir -p "$LOGDIR" "$PROPOSALS" "$LOCK_DIR"
TS=$(date +%Y%m%d-%H%M%S)

FLAGS=$(python3 - "$CONFIG" <<'PY'
import json,sys
cfg=json.load(open(sys.argv[1])); print(cfg.get("cron",{}).get("codex_flags","-s danger-full-access --dangerously-bypass-approvals-and-sandbox"))
PY
)
projects=$(python3 - "$CONFIG" <<'PY'
import json,sys
cfg=json.load(open(sys.argv[1])); print(" ".join(cfg["projects"].keys()))
PY
)

for project in $projects; do
  mode=$(python3 - "$CONFIG" "$project" <<'PY'
import json,sys
cfg=json.load(open(sys.argv[1])); print(cfg["projects"][sys.argv[2]].get("mode","propose"))
PY
)
  out="/tmp/rfbot_${project}_${TS}.json"
  count=$(python3 "$RFBOT" fetch --project "$project" --out "$out" 2>>"$LOGDIR/cron.log" || echo 0)
  if [ "${count:-0}" -le 0 ]; then
    echo "$(date -Is) [$project] aucun nouveau retour" >> "$LOGDIR/cron.log"
    rm -f "$out"; continue
  fi

  filt="/tmp/rfbot_${project}_${TS}_filt.json"
  python3 - "$project" "$out" "$filt" <<'PY'
import json, os, sys
project, out, filt = sys.argv[1], sys.argv[2], sys.argv[3]
items = json.load(open(out))
ap = os.path.expanduser("~/.codex-local/skills/ticket-driver/state/approvals.json")
appr = {}
if os.path.exists(ap): appr = json.load(open(ap))
sel = [i for i in items.get("items", []) if ("%s:%s" % (project, i.get("key"))) not in appr]
items["items"] = sel; items["count"] = len(sel)
json.dump(items, open(filt, "w"), indent=2); print(len(sel))
PY
  nfiltered=$(python3 -c "import json;print(json.load(open('$filt'))['count'])" 2>/dev/null || echo 0)
  if [ "${nfiltered:-0}" -le 0 ]; then
    echo "$(date -Is) [$project] retours déjà proposés/traités" >> "$LOGDIR/cron.log"
    rm -f "$out" "$filt"; continue
  fi

  if ! mkdir "$LOCK_DIR/$project" 2>/dev/null; then
    echo "$(date -Is) [$project] verrou présent, run déjà en cours — skip" >> "$LOGDIR/cron.log"
    rm -f "$out" "$filt"; continue
  fi
  trap 'rm -rf "$LOCK_DIR/$project"' EXIT

  repo=$(python3 - "$CONFIG" "$project" <<'PY'
import json,sys
cfg=json.load(open(sys.argv[1])); print(cfg["projects"][sys.argv[2]]["repo_dir"])
PY
)
  echo "$(date -Is) [$project] mode=$mode, $nfiltered nouveau(x) retour(s) -> $repo" >> "$LOGDIR/cron.log"

  if [ "$mode" = "signal" ]; then
    msg=$(python3 -c "import json;d=json.load(open('$filt'));print('\n'.join((i.get('url') or ('MR !%s'%i.get('mr_iid',''))) + ' — ' + (i.get('body') or '')[:140] for i in d['items']))" 2>/dev/null || echo "Nouveau retour sur $project")
    python3 "$TG" send-info --project "$project" --text "🔔 $project : nouveau retour de revue\n$msg" 2>>"$LOGDIR/cron.out" || true
    python3 - "$project" "$filt" <<'PY'
import json, os, sys
project, filt = sys.argv[1], sys.argv[2]
items = json.load(open(filt))
ap = os.path.expanduser("~/.codex-local/skills/ticket-driver/state/approvals.json")
appr = {}
if os.path.exists(ap): appr = json.load(open(ap))
for i in items["items"]: appr["%s:%s" % (project, i["key"])] = {"status": "signaled"}
json.dump(appr, open(ap, "w"), indent=2, sort_keys=True)
PY
  elif [ "$mode" = "propose" ]; then
    if [ "${RFBOT_DRY:-0}" = "1" ]; then
      echo "[DRY-RUN] propose: codex exec -C $repo $FLAGS (résumé modèle concis)"
    else
      "$CODEX" exec -C "$repo" $FLAGS \
        "Using the ticket-driver skill in PROPOSE mode, process the items in $filt. For each mr_comment (review) item: write a CONCISE summary (max ~300 chars, French) of the fix to be done; write state/proposals/<project>_<mr>.md with markers PROJECT, MR, TITLE, URL, DISCUSSION, TICKET, MARK_KEY, MARK_SUB, MARK_ID, SUMMARY. For each sprint_ticket (feat) item: produce a CLEAR DETAILED IMPLEMENTATION PLAN (French, structured: contexte, étapes, fichiers, PR attendue, tests) from the ticket + project skill; write state/proposals/<project>_<ticket_id>.md with markers PROJECT, TICKET, TITLE, URL, MARK_KEY, MARK_SUB, MARK_ID, SUMMARY (=the plan). Then send ONE Telegram approval per item via scripts/tg.py send-approval (project, mr-or-ticket, title, url, summary). Do NOT implement, do NOT push, do NOT reply/summary, do NOT journal Redmine. Escalate non-actionable items."
      python3 - "$project" "$filt" <<'PY'
import json, os, sys
project, filt = sys.argv[1], sys.argv[2]
items = json.load(open(filt))
ap = os.path.expanduser("~/.codex-local/skills/ticket-driver/state/approvals.json")
appr = {}
if os.path.exists(ap): appr = json.load(open(ap))
for i in items["items"]: appr["%s:%s" % (project, i["key"])] = {"status": "proposed"}
json.dump(appr, open(ap, "w"), indent=2, sort_keys=True)
PY
    fi
  else
    if [ "${RFBOT_DRY:-0}" = "1" ]; then
      echo "[DRY-RUN] auto: codex exec -C $repo $FLAGS avec $filt"
    else
      "$CODEX" exec -C "$repo" $FLAGS \
        "Using the ticket-driver skill, for the review feedback in $filt: apply the fix, run the project validation gate, commit and push, then report (reply/resolve/summary) on the MR/PR and journal the Redmine ticket. Mark items as processed afterwards. Escalate non-actionable/ambiguous/risky items."
    fi
  fi

  rm -f "$out" "$filt"
  rm -rf "$LOCK_DIR/$project"
  trap - EXIT
done

# --- Traiter les clics Telegram (✅/❌) ---
python3 "$TG" poll --once 2>>"$LOGDIR/cron.out" || true
