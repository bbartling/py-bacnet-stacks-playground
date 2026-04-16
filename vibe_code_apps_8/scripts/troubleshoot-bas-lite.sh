#!/usr/bin/env bash
# Smoke-test Caddy → nginx (SPA) + /app8/api from the host (Pi or laptop).
# Run on the edge host from the directory that contains docker-compose.yml (e.g. .../vibe_code_apps_8):
#   ./scripts/troubleshoot-bas-lite.sh
#   BAS_LITE_TROUBLESHOOT_URL=http://192.168.204.12:18080 ./scripts/troubleshoot-bas-lite.sh
#
# Optional: extra curl flags (TLS + Basic Auth, etc.):
#   BAS_LITE_TROUBLESHOOT_CURL_OPTS='-k -u operator:password' ./scripts/troubleshoot-bas-lite.sh
#
# Exit 0 = all checks passed; exit 1 = at least one failure.

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BASE="${BAS_LITE_TROUBLESHOOT_URL:-http://127.0.0.1:18080}"
BASE="${BASE%/}"
# shellcheck disable=SC2206
CURL_EXTRA=(${BAS_LITE_TROUBLESHOOT_CURL_OPTS:-})

fail=0
pass() { echo "  [ok] $*"; }
flunk() { echo "  [!!] $*" >&2; fail=1; }

http_get_body() {
  local url="$1" out="$2"
  curl -sS -L --connect-timeout 5 --max-time 60 "${CURL_EXTRA[@]}" -o "$out" -w '%{http_code}' "$url"
}

http_head_ct() {
  local url="$1"
  curl -sSI -L --connect-timeout 5 --max-time 30 "${CURL_EXTRA[@]}" "$url" | tr -d '\r' | awk -F': ' 'tolower($1)=="content-type" {print $2; exit}'
}

echo "=== BAS Lite troubleshoot (base: $BASE) ==="
echo "    (override URL: BAS_LITE_TROUBLESHOOT_URL=... )"
echo ""

tmp="$(mktemp "${TMPDIR:-/tmp}/bas-lite-smoke.XXXXXX")"
trap 'rm -f "$tmp" "${tmp}.html" "${tmp}.h.json" "${tmp}.css" 2>/dev/null' EXIT

code="$(http_get_body "$BASE/app8/" "${tmp}.html")"
if [[ "$code" != "200" ]]; then
  flunk "GET /app8/ returned HTTP $code (expected 200). Caddy down, wrong port, or path not proxied."
else
  pass "GET /app8/ HTTP 200"
fi

if [[ -f "${tmp}.html" ]]; then
  if ! grep -q 'id="root"' "${tmp}.html"; then
    flunk "/app8/ HTML missing <div id=\"root\"> (not the Vite shell?)"
  else
    pass "/app8/ contains #root mount point"
  fi
  if ! grep -q 'type="module"' "${tmp}.html"; then
    flunk "/app8/ HTML missing type=\"module\" script (broken index.html?)"
  else
    pass "/app8/ contains a module script tag"
  fi
else
  flunk "No response body for /app8/"
fi

js_path=""
if [[ -f "${tmp}.html" ]]; then
  # First module script src under /app8/assets/
  js_path="$(sed -n 's/.*<script[^>]*src="\(\/app8\/assets\/[^"]*\.js\)".*/\1/p' "${tmp}.html" | head -1)"
fi
if [[ -z "$js_path" ]]; then
  flunk "Could not parse Vite entry script from /app8/ (expected src=\"/app8/assets/....js\"). Rebuild with VITE_BASE_PATH=/app8."
else
  pass "Parsed entry script path: $js_path"
fi

if [[ -n "$js_path" ]]; then
  js_url="${BASE}${js_path}"
  ct="$(http_head_ct "$js_url")"
  if [[ -z "$ct" ]]; then
    flunk "HEAD $js_path - no Content-Type (connection refused or empty response?)"
  elif echo "$ct" | grep -qiE 'javascript|ecmascript|jscript'; then
    pass "HEAD entry script Content-Type looks like JS: ${ct%%;*}"
  elif echo "$ct" | grep -qi 'text/html'; then
    flunk "HEAD $js_path returned text/html (nginx SPA fallback or wrong URL - same symptom as blank React app)."
  else
    echo "  [??] entry script Content-Type: $ct (if the app loads, this may be fine)" >&2
  fi

  headc="$(curl -sS -L --connect-timeout 5 --max-time 60 "${CURL_EXTRA[@]}" "$js_url" | head -c 16)"
  if [[ -z "$headc" ]]; then
    flunk "GET entry script returned empty body."
  elif [[ "${headc:0:1}" == '<' ]]; then
    flunk "GET entry script body starts with '<' (HTML, not JS) - wrong URL or nginx served index.html instead of the bundle."
  else
    pass "GET entry script body does not look like HTML"
  fi
fi

css_path=""
if [[ -f "${tmp}.html" ]]; then
  css_path="$(grep -oE '/app8/assets/[^"]+\.css' "${tmp}.html" | head -1)"
fi
if [[ -n "$css_path" ]]; then
  ccode="$(http_get_body "${BASE}${css_path}" "${tmp}.css")"
  if [[ "$ccode" == "200" ]]; then
    pass "GET $css_path HTTP 200"
  else
    flunk "GET $css_path HTTP $ccode"
  fi
fi

echo ""
echo "=== API: /app8/api/health (retries while container starts) ==="
health_code=""
health_ok=0
for _ in $(seq 1 20); do
  health_code="$(curl -sS -L --connect-timeout 3 --max-time 15 "${CURL_EXTRA[@]}" -o "${tmp}.h.json" -w '%{http_code}' "$BASE/app8/api/health" || true)"
  if [[ "$health_code" == "200" ]] && [[ -s "${tmp}.h.json" ]]; then
    if grep -q '"status"' "${tmp}.h.json" 2>/dev/null; then
      health_ok=1
      break
    fi
  fi
  sleep 2
done
if [[ "$health_ok" -eq 1 ]]; then
  pass "/app8/api/health HTTP 200 and JSON contains \"status\""
  head -c 240 "${tmp}.h.json" | tr -d '\n'
  echo ""
else
  flunk "/app8/api/health not usable after retries (last HTTP=$health_code). Is api healthy? docker compose logs api --tail 80"
fi

echo ""
echo "=== SPA deep links (nginx should still return shell HTML) ==="
for path in /app8/live-points /app8/system /app8/driver; do
  c="$(http_get_body "$BASE$path" "$tmp")"
  if [[ "$c" == "200" ]] && grep -q 'id="root"' "$tmp" 2>/dev/null; then
    pass "GET $path HTTP 200 and contains #root"
  else
    flunk "GET $path expected 200 + #root shell, got HTTP=$c"
  fi
done

echo ""
if [[ "$fail" -eq 0 ]]; then
  echo "=== Summary: all checks passed ==="
  exit 0
fi
echo "=== Summary: one or more checks failed (see [!!] above) ===" >&2
echo "Hints: blank browser + 'module script MIME text/html' → entry JS URL returned HTML (missing asset or wrong base path)." >&2
echo "Re-run: docker compose logs caddy --tail 40; docker compose logs frontend --tail 40; docker compose exec frontend ls -la /usr/share/nginx/html/app8/assets" >&2
exit 1
