#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/env.sh"

CAMPUS_IP="${CAMPUS_IP:-$HOST_IP}"
BUILDING_LOCAL_IP="${BUILDING_LOCAL_IP:-}"
VAV_IP="${VAV_IP:-192.168.204.14}"
AHU_IP="${AHU_IP:-192.168.0.13}"

if [[ -z "$BUILDING_LOCAL_IP" ]]; then
  base="${CAMPUS_IP%.*}"
  last="${CAMPUS_IP##*.}"
  BUILDING_LOCAL_IP="${base}.$((last + 10))"
fi

OUT="${1:-$ROOT/config/campus-full-router.rendered.json}"
sed -e "s/__CAMPUS_IP__/${CAMPUS_IP}/g" \
  -e "s/__BUILDING_LOCAL_IP__/${BUILDING_LOCAL_IP}/g" \
  -e "s/__VAV_IP__/${VAV_IP}/g" \
  -e "s/__AHU_IP__/${AHU_IP}/g" \
  "$ROOT/config/campus-full-router.template.json" >"$OUT"
echo "wrote $OUT"
echo "  net 100 campus      ${CAMPUS_IP}:47808"
echo "  net 200 mini        ${BUILDING_LOCAL_IP}:47809"
echo "  net 201 VAV         ${VAV_IP}:47808"
echo "  net 202 AHU         ${AHU_IP}:47808"
