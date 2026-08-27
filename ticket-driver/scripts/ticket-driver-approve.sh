#!/bin/bash
# Finalise après ✅ : implémente le fix (codex exec), valide, pousse, répond/résout la MR,
# journalise Redmine et marque. Idempotent : ne re-traitete pas un item déjà traité.
# Usage : ticket-driver-approve.sh <projet> <mr>
set -euo pipefail
SKILL_DIR="$HOME/.codex-local/skills/ticket-driver"
CONFIG="$SKILL_DIR/state/config.json"
CODEX=/home/y-note/bin/codex
PROJECT="${1:?projet requis}"
MR="${2:?mr requis}"
PROP="$SKILL_DIR/state/proposals/${PROJECT}_${MR}.md"
APPROVALS="$SKILL_DIR/state/approvals.json"

[ -f "$PROP" ] || { echo "proposition introuvable: $PROP"; exit 1; }
read_attr() { grep -m1 "^$1:" "$PROP" | sed "s/^$1://" | sed 's/^ *//;s/ *$//'; }
TITLE=$(read_attr TITLE); URL=$(read_attr URL); SUMMARY=$(read_attr SUMMARY)
DISCUSSION=$(read_attr DISCUSSION); TICKET=$(read_attr TICKET)
MARK_KEY=$(read_attr MARK_KEY); MARK_SUB=$(read_attr MARK_SUB); MARK_ID=$(read_attr MARK_ID)
repo=$(python3 - "$CONFIG" "$PROJECT" <<'PY'
import json,sys
cfg=json.load(open(sys.argv[1])); print(cfg["projects"][sys.argv[2]]["repo_dir"])
PY
)
FLAGS=$(python3 - "$CONFIG" <<'PY'
import json,sys
cfg=json.load(open(sys.argv[1])); print(cfg.get("cron",{}).get("codex_flags","-s danger-full-access --dangerously-bypass-approvals-and-sandbox"))
PY
)

echo "APPROVE $PROJECT !$MR -> codex exec (implémentation + push + report)" >&2
STATUS=proposed
# shellcheck disable=SC2086
if "$CODEX" exec -C "$repo" $FLAGS \
  "Using the ticket-driver skill, implement the task described in $PROP (markers PROJECT=$PROJECT MR=$MR TITLE='$TITLE' URL='$URL' DISCUSSION='$DISCUSSION' TICKET='$TICKET' MARK_KEY='$MARK_KEY' MARK_SUB='$MARK_SUB' MARK_ID='$MARK_ID' SUMMARY='$SUMMARY'). If TICKET is a feature/sprint ticket (no review discussion): read the ticket, follow the project skill (openimis-feature/mi/...), create a worktree/branch feature-$TICKET, implement, run the project validation gate, push, open the PR, and journal the Redmine ticket to recette. If it is a review-fix (MR): apply the fix, validate, push, then reply/resolve/summary on the MR ($PROJECT !$MR) and journal the Redmine ticket (${TICKET:-none}). Mark the item via mark-key --project $PROJECT --key $MARK_KEY --sub ${MARK_SUB:-processed_notes} --id $MARK_ID. Escalate if non-actionable/ambigu/risqué."; then
  STATUS=approved
else
  STATUS=proposed
  echo "ÉCHEC approve $PROJECT !$MR (voir logs) — statut remis à proposed" >&2
fi

python3 - "$PROJECT" "$MR" "$APPROVALS" "$STATUS" <<'PY'
import json, os, sys
project, mr, p, status = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
st = {}
if os.path.exists(p):
    with open(p) as f: st = json.load(f)
st["%s:gitlab_mr_%s" % (project, mr)] = {"status": status}
with open(p, "w") as f: json.dump(st, f, indent=2, sort_keys=True)
PY

if [ "$STATUS" = "approved" ]; then
  echo "approuvé & appliqué: $PROJECT !$MR"
else
  exit 1
fi
