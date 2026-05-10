#!/usr/bin/env bash
# One-shot: does `codex exec` run a trivial shell under the current sandbox settings?
# Exit 0 = OK, 1 = bwrap / sandbox failure (set CODEX_DANGEROUSLY_BYPASS=true on isolated hosts).
set -euo pipefail
BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRON_ROOT="$(cd "$BIN_DIR/.." && pwd)"
BAS_BUILD="$(cd "$BIN_DIR/../.." && pwd)"
REPO_DEFAULT="$(cd "$BAS_BUILD/.." && pwd)"
ENV_FILE="${BAS_CODEX_ENV_FILE:-$CRON_ROOT/.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=1090
  source "$ENV_FILE"
  set +a
fi
: "${CODEX_CWD:=$REPO_DEFAULT}"
: "${CODEX_SANDBOX:=workspace-write}"
: "${CODEX_DANGEROUSLY_BYPASS:=false}"

args=(exec -C "$CODEX_CWD" -s "$CODEX_SANDBOX" --skip-git-repo-check --color never)
if [[ "${CODEX_DANGEROUSLY_BYPASS,,}" == "true" ]]; then
  args+=(--dangerously-bypass-approvals-and-sandbox)
fi

echo "Probing: codex ${args[*]} 'echo CODEX_PROBE_OK'"
out="$(codex "${args[@]}" "Run only: echo CODEX_PROBE_OK" 2>&1)" || true
echo "$out"
if echo "$out" | grep -q 'CODEX_PROBE_OK'; then
  echo "RESULT: sandbox OK"
  exit 0
fi
if echo "$out" | grep -q 'bwrap:.*RTM_NEWADDR\|Operation not permitted'; then
  echo "RESULT: FAIL (bubblewrap / namespace). In cron_codex/.env set CODEX_DANGEROUSLY_BYPASS=true on an isolated build host, or fix LXC/seccomp/AppArmor."
  exit 1
fi
echo "RESULT: UNKNOWN (see output above)"
exit 2
