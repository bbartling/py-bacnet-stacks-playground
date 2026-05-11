# Shared helpers for bas_validate_*.sh (source only; not executed directly).
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "source bas_validate_common.sh from a validate script" >&2
  exit 2
fi

BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)"
CRON_ROOT="$(cd "$BIN_DIR/.." && pwd)"
BAS_BUILD="$(cd "$BIN_DIR/../.." && pwd)"
BAS_APP="$(cd "$BAS_BUILD/.." && pwd)/bas_app"
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

: "${BAS_CODEX_LOCK:=/tmp/bas_codex_wake.lock}"
: "${BAS_CODEX_LOG_DIR:=$CRON_ROOT/logs}"
: "${BAS_BACKEND_HEALTH_URL:=http://127.0.0.1:8000/health}"
: "${BAS_FRONTEND_HEALTH_URL:=http://127.0.0.1:5173/}"
