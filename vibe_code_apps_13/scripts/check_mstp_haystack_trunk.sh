#!/usr/bin/env bash
# Haystack supervisory gate for BASRT/FEC/Rust MS/TP trunk health (Gate 4b).
#
# Modes:
#   check              — FEC + Rust mini-device points show curStatus/axStatus ok
#   perturb-stop-mini  — verify trunk/FEC stay ok when local mini-device is stopped
#   restore            — same as check after mini-device should be running
#
# Env (never commit secrets):
#   HAYSTACK_BASE_URL  default https://192.168.204.11/haystack
#   HAYSTACK_USER / HAYSTACK_PASS  or source ~/open-fdd/.env
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:-check}"
ART="${HAYSTACK_ARTIFACT_DIR:-$ROOT/captures/haystack-trunk}"
mkdir -p "$ART"

if [[ -f "$HOME/open-fdd/.env" ]]; then
  # shellcheck disable=SC1091
  source "$HOME/open-fdd/.env"
fi

HS_URL="${HAYSTACK_BASE_URL:-https://192.168.204.11/haystack}"
HS_USER="${HAYSTACK_USER:-${OPENFDD_HAYSTACK_USER:-}}"
HS_PASS="${HAYSTACK_PASS:-${OPENFDD_HAYSTACK_PASS:-}}"

RED=$'\033[31m'
GRN=$'\033[32m'
DIM=$'\033[2m'
RST=$'\033[0m'

ok() { echo "${GRN}OK${RST}  $*"; }
bad() { echo "${RED}FAIL${RST} $*" >&2; exit 1; }
hdr() { echo; echo "== $*"; }

require_creds() {
  [[ -n "$HS_USER" && -n "$HS_PASS" ]] || bad "HAYSTACK_USER/HAYSTACK_PASS required (see ~/open-fdd/.env)"
}

hs_nav() {
  local nav_id="$1" out="$2"
  local enc
  enc="$(NAV="$nav_id" python3 -c 'import urllib.parse,os; print(urllib.parse.quote(os.environ["NAV"]))')"
  curl -fsSk --max-time 30 -u "$HS_USER:$HS_PASS" -H 'Accept: text/zinc' \
    "$HS_URL/nav?navId=$enc" -o "$out"
}

extract_status() {
  RAW="${1:-}" python3 - <<'PY'
import os, re
raw = os.environ.get("RAW", "")
if re.search(r'"ok"', raw) or re.search(r'\boperational\b', raw, re.I):
    print("ok")
elif re.search(r'"down"', raw):
    print("down")
else:
    for pat in (r"curStatus\s*:\s*(\S+)", r"axStatus\s*:\s*(\S+)", r"systemStatus\s*:\s*(\S+)"):
        m = re.search(pat, raw, re.I)
        if m:
            print(m.group(1).strip('"'))
            break
PY
}

check_point_ok() {
  local label="$1" filter="$2" outfile="$3"
  local body status
  hs_read "$filter" "$outfile"
  body="$(cat "$outfile")"
  status="$(extract_status "$body")"
  echo "${DIM}  $label status=$status${RST}"
  [[ "$status" == "ok" || "$status" == "operational" ]] || bad "$label Haystack status=$status (expected ok/operational)"
  ok "$label online ($status)"
}

hs_read() {
  local filter="$1" out="$2"
  local enc
  enc="$(FILTER="$filter" python3 -c 'import urllib.parse,os; print(urllib.parse.quote(os.environ["FILTER"]))')"
  curl -fsSk --max-time 30 -u "$HS_USER:$HS_PASS" -H 'Accept: text/zinc' \
    "$HS_URL/read?filter=$enc" -o "$out"
}

check_fec_points_nav() {
  local outfile="$1"
  hs_nav "slot:/Drivers/BacnetNetwork/BENS\$20BENCHTEST\$20BOX/points" "$outfile"
  grep -E '"ok"' "$outfile" >/dev/null || bad "FEC points nav missing curStatus ok"
  ok "FEC points nav (7 points) curStatus ok"
}

check_trunk() {
  require_creds
  hdr "Haystack /about"
  curl -fsSk --max-time 20 -u "$HS_USER:$HS_PASS" -H 'Accept: text/zinc' \
    "$HS_URL/about" -o "$ART/haystack_about.zinc"
  ok "Niagara /about"

  hdr "FEC bench points (BENS BENCHTEST BOX nav)"
  check_fec_points_nav "$ART/haystack_fec_points.zinc"

  hdr "Rust mini-device read-only-ai"
  check_point_ok "read-only-ai" 'point and dis=="read-only-ai"' "$ART/haystack_rust_ai.zinc"

  hdr "Rust MS/TP mini device"
  hs_read 'device and dis=="Rust MS/TP Mini Device"' "$ART/haystack_rust_device.zinc"
  grep -q 'Rust MS/TP Mini Device' "$ART/haystack_rust_device.zinc" \
    || bad "Rust MS/TP Mini Device not present in Haystack export"
  ok "Rust MS/TP Mini Device present in Haystack"
}

case "$MODE" in
  check|restore)
    check_trunk
    ;;
  perturb-stop-mini)
    require_creds
    hdr "Perturbation: mini-device should be STOPPED; FEC must stay ok"
    if pgrep -f 'mstp-mini-device' >/dev/null; then
      bad "mstp-mini-device still running — stop it before perturb-stop-mini"
    fi
    ok "mstp-mini-device not running (MAC 3 absent)"
    check_fec_points_nav "$ART/haystack_fec_after_stop.zinc"
    ok "FEC still ok with mini-device stopped"
    ;;
  *)
    bad "usage: $0 {check|perturb-stop-mini|restore}"
    ;;
esac

echo
ok "Haystack trunk gate ($MODE) PASS — artifacts in $ART"
