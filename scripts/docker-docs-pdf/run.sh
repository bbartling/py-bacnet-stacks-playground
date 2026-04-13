#!/usr/bin/env bash
# Run from repo root with /work = repo (see README). Builds bundled PDFs for known apps.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

run_one() {
  local app="$1"
  local title="$2"
  local docs="${ROOT}/${app}/docs"
  local out="${ROOT}/${app}/documentation.pdf"
  if [[ ! -d "$docs" ]]; then
    echo "skip (no docs dir): $docs" >&2
    return 0
  fi
  echo "==> $app -> $out"
  python3 "${ROOT}/scripts/build_docs_pdf.py" \
    --docs-dir "$docs" \
    --title "$title" \
    -o "$out"
}

run_one "vibe_code_apps_7" "Vibe code app 7"
run_one "vibe_code_apps_8" "Vibe code app 8 (BAS Lite)"

echo "Done."
