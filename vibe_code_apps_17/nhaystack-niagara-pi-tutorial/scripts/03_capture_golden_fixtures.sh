#!/usr/bin/env bash
# Capture golden nHaystack responses from live Niagara 4.15 station.
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -f ".env" ]]; then
  # shellcheck disable=SC1091
  source ".env"
fi

: "${HAYSTACK_BASE:?Set HAYSTACK_BASE}"
: "${HAYSTACK_USER:?Set HAYSTACK_USER}"
: "${HAYSTACK_PASS:?Set HAYSTACK_PASS}"

OUT="fixtures/golden"
mkdir -p "$OUT"

echo "Capturing to $(pwd)/$OUT"

curl -k -sS -D "$OUT/about.headers.txt" -o "$OUT/about.zinc" \
  -u "$HAYSTACK_USER:$HAYSTACK_PASS" \
  -H "Accept: text/zinc" \
  "$HAYSTACK_BASE/about"

curl -k -sS -o "$OUT/ops.zinc" \
  -u "$HAYSTACK_USER:$HAYSTACK_PASS" \
  -H "Accept: text/zinc" \
  "$HAYSTACK_BASE/ops"

curl -k -sS -o "$OUT/read_point_and_cur.csv" \
  -u "$HAYSTACK_USER:$HAYSTACK_PASS" \
  -H "Accept: text/csv" \
  --get "$HAYSTACK_BASE/read" \
  --data-urlencode "filter=point and cur"

# SCRAM HELLO probe (document that Niagara does not challenge)
USER_B64="$(printf '%s' "$HAYSTACK_USER" | base64 -w0 2>/dev/null || printf '%s' "$HAYSTACK_USER" | base64)"
NONCE="$(openssl rand -hex 8)"
CLIENT_FIRST="$(printf 'n=%s,r=%s' "$HAYSTACK_USER" "$NONCE" | base64 -w0 2>/dev/null || printf 'n=%s,r=%s' "$HAYSTACK_USER" "$NONCE" | base64)"
curl -k -sS -D "$OUT/scram_hello.headers.txt" -o "$OUT/scram_hello.body.txt" \
  -H "Authorization: HELLO username=${USER_B64}, data=${CLIENT_FIRST}" \
  "$HAYSTACK_BASE/about"

TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
cat >"$OUT/manifest.json" <<EOF
{
  "captured_at_utc": "$TS",
  "haystack_base": "$HAYSTACK_BASE",
  "haystack_user": "$HAYSTACK_USER",
  "platform": "Niagara 4 (N4)",
  "notes": "Golden fixtures for nHaystack API fixture server. Password not stored.",
  "files": [
    "about.zinc",
    "about.headers.txt",
    "ops.zinc",
    "read_point_and_cur.csv",
    "scram_hello.headers.txt",
    "scram_hello.body.txt"
  ]
}
EOF

echo "Done. Review $OUT/manifest.json"
wc -l "$OUT"/* 2>/dev/null | tail -5
