#!/usr/bin/env bash
# Verify wake-to-wake rough-in chat slice exists, includes pinned notepad, and matches chat + jobs-state.
set -euo pipefail

BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRON_ROOT="$(cd "$BIN_DIR/.." && pwd)"
BAS_BUILD="$(cd "$BIN_DIR/../.." && pwd)"

ENV_FILE="${BAS_CODEX_ENV_FILE:-$CRON_ROOT/.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=1090
  source "$ENV_FILE"
  set +a
fi

BAS_APP="${BAS_APP:-/home/ben/bas_app}"
CHAT_PATH="${BAS_COMMISSIONING_CHAT_PATH:-$BAS_APP/runtime/rough_in_chat.json}"
JOBS_STATE="$BAS_BUILD/cron/jobs-state.json"
PHASE_NOTEPAD="$BAS_BUILD/memory/commissioning/PHASE_NOTEPAD.md"
SLICE_MD="$CRON_ROOT/state/rough_in_chat_since_last_wake.md"
SLICE_META="$CRON_ROOT/state/rough_in_chat_since_last_wake.meta.json"

bad() {
  echo "FAIL: $*" >&2
  exit 1
}

[[ -f "$CHAT_PATH" ]] || bad "chat file missing: $CHAT_PATH"
[[ -f "$JOBS_STATE" ]] || bad "jobs-state missing: $JOBS_STATE"
[[ -f "$PHASE_NOTEPAD" ]] || bad "PHASE_NOTEPAD missing: $PHASE_NOTEPAD"
[[ -f "$SLICE_MD" ]] || bad "slice missing: $SLICE_MD (run bas_wake_prepare.sh or bas_wake first)"
[[ -f "$SLICE_META" ]] || bad "slice meta missing: $SLICE_META"

python3 "$BIN_DIR/bas_rough_in_chat_since_wake.py" \
  "$CHAT_PATH" "$JOBS_STATE" "$SLICE_MD" "$SLICE_META" "$PHASE_NOTEPAD" >/dev/null

grep -q "Pinned site context" "$SLICE_MD" || bad "slice missing pinned notepad section"
grep -q "Chat since last bas_wake" "$SLICE_MD" || bad "slice missing chat window section"
grep -q "## A) BACnet bind" "$SLICE_MD" || bad "slice missing notepad § A header"

meta_count="$(python3 -c "import json; m=json.load(open('$SLICE_META')); print(m['message_count'])")"
notepad_pinned="$(python3 -c "import json; print(json.load(open('$SLICE_META')).get('notepad_pinned'))")"
[[ "$notepad_pinned" == "True" ]] || bad "meta notepad_pinned is not true"

# Site-specific: notepad § A must have a real bind (table uses backticks around values)
python3 - "$PHASE_NOTEPAD" <<'PY' || bad "PHASE_NOTEPAD § A bind not filled"
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
section = text.split("## A)")[1].split("## B)")[0] if "## A)" in text else ""
if not re.search(r"BACnet bind string", section):
    raise SystemExit(1)
if re.search(r"\(fill\)", section) and not re.search(r":47808|/\d{1,2}:", section):
    raise SystemExit(1)
if not re.search(r"\d+\.\d+\.\d+\.\d+", section):
    raise SystemExit(1)
PY

echo "ok: slice message_count=$meta_count notepad_pinned=$notepad_pinned"
echo "slice: $SLICE_MD"
echo "meta:  $SLICE_META"
head -n 20 "$SLICE_MD"
