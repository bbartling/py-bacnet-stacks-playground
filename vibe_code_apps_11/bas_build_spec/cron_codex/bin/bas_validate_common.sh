# Shared helpers for bas_validate_*.sh (source only; not executed directly).
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "source bas_validate_common.sh from a validate script" >&2
  exit 2
fi

BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)"
CRON_ROOT="$(cd "$BIN_DIR/.." && pwd)"
BAS_BUILD="$(cd "$BIN_DIR/../.." && pwd)"
ENV_FILE="${BAS_CODEX_ENV_FILE:-$CRON_ROOT/.env}"
MARKER="${CRON_MARKER:-BAS_CODEX_WAKE}"
FAIL=0

ok() { echo "OK  $*"; }
warn() { echo "WARN $*"; FAIL=1; }
bad() { echo "FAIL $*"; FAIL=1; }
info() { echo "    $*"; }

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=1090
  source "$ENV_FILE"
  set +a
fi

# bas_app: BAS_APP or BAS_APP_DIR in .env; else ../bas_app next to this bas_build_spec directory
if [[ -n "${BAS_APP_DIR:-}" ]]; then
  BAS_APP="$(cd "$BAS_APP_DIR" && pwd)"
elif [[ -n "${BAS_APP:-}" ]]; then
  BAS_APP="$(cd "$(dirname "$BAS_APP")" && pwd)/$(basename "$BAS_APP")"
else
  BAS_APP="$(cd "$BAS_BUILD/.." && pwd)/bas_app"
fi

: "${BAS_CODEX_LOCK:=/tmp/bas_codex_wake.lock}"
: "${BAS_CODEX_LOG_DIR:=$CRON_ROOT/logs}"
: "${BAS_BACKEND_HEALTH_URL:=http://127.0.0.1:8000/health}"
: "${BAS_FRONTEND_HEALTH_URL:=http://127.0.0.1:5173/}"

user_systemd_reachable() {
  systemctl --user is-system-running &>/dev/null
}
