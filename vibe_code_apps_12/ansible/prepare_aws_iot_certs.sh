#!/usr/bin/env bash
# Copy device cert/key from aws_iot_core_test (unzipped connect package) into ansible/files/aws_iot/
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${ROOT}/aws_iot_core_test"
DEST="${ROOT}/ansible/files/aws_iot"
CERT="vibe-code-app-12-temp-sensor.cert.pem"
KEY="vibe-code-app-12-temp-sensor.private.key"

mkdir -p "$DEST"
for f in "$CERT" "$KEY"; do
  if [[ ! -f "${SRC}/${f}" ]]; then
    echo "Missing ${SRC}/${f}" >&2
    echo "Unzip connect_device_package.zip in aws_iot_core_test/ first." >&2
    exit 1
  fi
  cp -f "${SRC}/${f}" "${DEST}/${f}"
  echo "Copied ${f} -> ${DEST}/"
done
chmod 600 "${DEST}/${KEY}"
chmod 644 "${DEST}/${CERT}"
