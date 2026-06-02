#!/usr/bin/env bash
# Run vibe_code_apps_12 Python unit tests (matches CI: requirements.txt + web_lambda deps).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="${ROOT}/.test_venv"

if [[ ! -x "${VENV}/bin/python" ]]; then
  echo "Creating ${VENV} ..."
  python3 -m venv "$VENV"
fi

"${VENV}/bin/pip" install -q -U pip
"${VENV}/bin/pip" install -q \
  -r "${ROOT}/requirements.txt" \
  -r "${ROOT}/aws_cloud_pipeline/web_lambda/requirements.txt"

echo "Running unittest discover ..."
"${VENV}/bin/python" -m unittest discover -s "${ROOT}/tests" -v
