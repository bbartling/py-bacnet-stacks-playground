#!/usr/bin/env bash
# Fast sanity check before first wake: paths, helper scripts, optional codex.
set -euo pipefail
BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRON_ROOT="$(cd "$BIN_DIR/.." && pwd)"
BAS_BUILD="$(cd "$BIN_DIR/../.." && pwd)"
ERR=0

ENV_FILE="${BAS_CODEX_ENV_FILE:-$CRON_ROOT/.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=1090
  source "$ENV_FILE"
  set +a
fi
warn() { echo "WARN: $*"; ERR=1; }
fail() { echo "FAIL: $*"; exit 1; }

echo "== bas_smoke =="
echo "BAS_BUILD=$BAS_BUILD CRON_ROOT=$CRON_ROOT"

[[ -f "$BAS_BUILD/spec.md" ]] || fail "missing spec.md"
[[ -f "$BAS_BUILD/acceptance_criteria.md" ]] || fail "missing acceptance_criteria.md"
[[ -f "$BAS_BUILD/skills/README.md" ]] || fail "missing skills/README.md"
[[ -f "$BAS_BUILD/skills/GUARDRAILS.md" ]] || fail "missing skills/GUARDRAILS.md"
[[ -f "$CRON_ROOT/env.example" ]] || fail "missing env.example"

for x in bas_wake.sh check_acceptance_complete.sh bas_remove_cron_marked.sh bas_smoke.sh bas_skills_link.sh; do
  [[ -x "$BIN_DIR/$x" ]] || warn "not executable: $BIN_DIR/$x (chmod +x)"
done

repo_skills="$(find "$BAS_BUILD/skills" -mindepth 2 -maxdepth 2 -name SKILL.md 2>/dev/null | wc -l)"
echo "repo SKILL.md files under bas_build_spec/skills/: $repo_skills"

if ! command -v codex &>/dev/null; then
  warn "codex not in PATH — install/login before bas_wake.sh"
else
  echo "codex: $(command -v codex)"
fi

if [[ -d "$HOME/.cursor/skills" ]]; then
  n=$(find -L "$HOME/.cursor/skills" -maxdepth 2 -name 'SKILL.md' 2>/dev/null | wc -l)
  echo "Cursor skills (~/.cursor/skills, symlinks followed): $n SKILL.md"
else
  warn "no ~/.cursor/skills — run bas_skills_link.sh after adding skills"
fi

if "$BIN_DIR/check_acceptance_complete.sh" "$BAS_BUILD/acceptance_criteria.md" 2>/dev/null; then
  echo "acceptance: COMPLETE (per check_acceptance_complete.sh — marker or legacy checklist)"
else
  echo "acceptance: incomplete (expected during build)"
fi

if [[ -n "${BAS_SMOKE_GET_URLS:-}" ]]; then
  echo "== optional HTTP smoke (BAS_SMOKE_GET_URLS) =="
  timeout_s="${BAS_SMOKE_CURL_TIMEOUT:-15}"
  # shellcheck disable=2086
  for url in $BAS_SMOKE_GET_URLS; do
    [[ -n "$url" ]] || continue
    echo "GET $url"
    curl -sfS --max-time "$timeout_s" -o /dev/null "$url" || fail "curl failed: $url"
  done
  echo "HTTP smoke OK"
fi

echo "== bas_smoke done (exit $ERR) =="
exit "$ERR"
