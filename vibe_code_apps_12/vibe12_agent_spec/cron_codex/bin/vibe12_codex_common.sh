#!/usr/bin/env bash
# Shared Codex exec flags for vibe12_wake / TUI hosts.
set -euo pipefail

vibe12_load_env() {
  local cron_root="${1:?}"
  local env_file="${VIBE12_CODEX_ENV_FILE:-$cron_root/.env}"
  if [[ -f "$env_file" ]]; then
    set -a
    # shellcheck disable=1090
    source "$env_file"
    set +a
  fi
  : "${MINI_MODEL:=gpt-5.4-mini}"
  : "${CRITIQUE_MODEL:=gpt-5.5}"
  : "${MINI_INVOCATIONS_PER_WAKE:=3}"
  : "${MINI_ALLOW_EARLY_STOP:=true}"
  : "${SLEEP_BETWEEN_MINI_SEC:=2}"
  : "${SKIP_CRITIQUE_WHEN_CLEAN:=false}"
  : "${CODEX_DANGEROUSLY_BYPASS:=false}"
}

vibe12_bwrap_ok() {
  command -v bwrap >/dev/null 2>&1 || return 1
  bwrap --ro-bind / / --dev /dev --unshare-net -- true >/dev/null 2>&1
}

vibe12_codex_sandbox_args() {
  local -n _out=$1
  _out=()
  if [[ "${VIBE12_CODEX_BYPASS_SANDBOX,,}" == "true" ]] \
    || [[ "${CODEX_DANGEROUSLY_BYPASS,,}" == "true" ]]; then
    _out+=(--dangerously-bypass-approvals-and-sandbox)
    return 0
  fi
  if [[ -n "${VIBE12_CODEX_SANDBOX+x}" ]]; then
    local mode="${VIBE12_CODEX_SANDBOX}"
    if [[ -n "$mode" && "$mode" != "none" ]]; then
      _out+=(-s "$mode")
    fi
    return 0
  fi
  if [[ -n "${CODEX_SANDBOX:-}" ]]; then
    _out+=(-s "$CODEX_SANDBOX")
    return 0
  fi
  if ! vibe12_bwrap_ok; then
    _out+=(--dangerously-bypass-approvals-and-sandbox)
    return 0
  fi
  _out+=(-s workspace-write)
}
