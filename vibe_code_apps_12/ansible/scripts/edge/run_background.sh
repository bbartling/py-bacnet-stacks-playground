#!/usr/bin/env bash
# Run another edge script in background; write pid + log under ~/vibe_code_apps_12/jobs/.
# Usage: run_background.sh <job_name> <script> [args...]
set -euo pipefail
JOB_NAME="${1:?job name}"
SCRIPT="${2:?script path}"
shift 2

APP_DIR="${VIBE12_APP_DIR:-${HOME}/vibe_code_apps_12}"
export PYTHONPATH="${APP_DIR}${PYTHONPATH:+:${PYTHONPATH}}"
JOBS="${APP_DIR}/jobs"
mkdir -p "${JOBS}"

LOG="${JOBS}/${JOB_NAME}.log"
PIDFILE="${JOBS}/${JOB_NAME}.pid"
STATUS="${JOBS}/${JOB_NAME}.status"

if [[ -f "${PIDFILE}" ]]; then
  old_pid="$(cat "${PIDFILE}")"
  if kill -0 "${old_pid}" 2>/dev/null; then
    echo "Job ${JOB_NAME} already running (pid ${old_pid}). Log: ${LOG}" >&2
    exit 1
  fi
fi

echo "running" > "${STATUS}"
nohup "${SCRIPT}" "$@" >> "${LOG}" 2>&1 &
echo $! > "${PIDFILE}"
echo "Started ${JOB_NAME} pid=$(cat "${PIDFILE}") log=${LOG}"
