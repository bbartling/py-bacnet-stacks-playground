# Sourced by edge commissioning scripts on the gateway VM.
APP_DIR="${VIBE12_APP_DIR:-${HOME}/vibe_code_apps_12}"
export PYTHONPATH="${APP_DIR}${PYTHONPATH:+:${PYTHONPATH}}"
PYTHON="${APP_DIR}/.venv/bin/python"
ENV_FILE="${APP_DIR}/commissioning_agent.env"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

BACNET_NAME="${BACNET_NAME:-Gateway}"
BACNET_INSTANCE="${BACNET_INSTANCE:-3456788}"
BACNET_BIND="${BACNET_BIND:-0.0.0.0/24:47808}"
SITE_ID="${SITE_ID:-demo}"
BUILDING_ID="${BUILDING_ID:-pi}"
DISCOVER_LOW="${DISCOVER_LOW:-0}"
DISCOVER_HIGH="${DISCOVER_HIGH:-9999}"
DISCOVER_TIMEOUT="${DISCOVER_TIMEOUT:-20}"
ROUTER_IP="${ROUTER_IP:-}"
MSTP_NET="${MSTP_NET:-}"
BACNET_NETWORK="${BACNET_NETWORK:-1}"

ROUTER_ARGS=()
if [[ -n "${ROUTER_IP}" && -n "${MSTP_NET}" ]]; then
  ROUTER_ARGS+=(--route-aware --network "${BACNET_NETWORK}" --router-ip "${ROUTER_IP}" --mstp-net "${MSTP_NET}")
fi

COMMON_ARGS=(
  --site-id "${SITE_ID}"
  --building-id "${BUILDING_ID}"
  --name "${BACNET_NAME}"
  --instance "${BACNET_INSTANCE}"
  --address "${BACNET_BIND}"
)
