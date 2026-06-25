#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -f ".env" ]]; then
  # shellcheck disable=SC1091
  source ".env"
fi

: "${HAYSTACK_BASE:?Set HAYSTACK_BASE, example: https://192.168.204.11/haystack}"
: "${HAYSTACK_USER:?Set HAYSTACK_USER}"
: "${HAYSTACK_PASS:?Set HAYSTACK_PASS}"

cargo run
