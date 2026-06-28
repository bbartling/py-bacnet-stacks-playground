#!/usr/bin/env bash
# Compare Niagara nHaystack HTTP Basic vs Project Haystack SCRAM HELLO.
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -f ".env" ]]; then
  # shellcheck disable=SC1091
  source ".env"
fi

: "${HAYSTACK_BASE:?Set HAYSTACK_BASE}"
: "${HAYSTACK_USER:?Set HAYSTACK_USER}"
: "${HAYSTACK_PASS:?Set HAYSTACK_PASS}"

echo "== HTTP Basic /about (Niagara API path) =="
curl -k -sS -o /dev/null -w "status: %{http_code}\n" \
  -u "$HAYSTACK_USER:$HAYSTACK_PASS" \
  "$HAYSTACK_BASE/about"

echo
echo "== SCRAM HELLO /about (SkySpark / rusty-haystack server path) =="
USER_B64="$(printf '%s' "$HAYSTACK_USER" | base64 -w0 2>/dev/null || printf '%s' "$HAYSTACK_USER" | base64)"
NONCE="$(openssl rand -hex 8)"
CLIENT_FIRST="$(printf 'n=%s,r=%s' "$HAYSTACK_USER" "$NONCE" | base64 -w0 2>/dev/null || printf 'n=%s,r=%s' "$HAYSTACK_USER" "$NONCE" | base64)"
curl -k -sS -D - -o /dev/null \
  -H "Authorization: HELLO username=${USER_B64}, data=${CLIENT_FIRST}" \
  "$HAYSTACK_BASE/about" | head -15

echo
echo "Expect: Basic → 200. SCRAM HELLO → 401 with NO 'WWW-Authenticate: SCRAM' on nHaystack 3.3."
