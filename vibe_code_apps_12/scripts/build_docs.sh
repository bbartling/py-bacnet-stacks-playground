#!/usr/bin/env bash
# Build vibe12-edge-fdd-guide.pdf (and .txt). Requires pandoc + .docs-venv.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ ! -x .docs-venv/bin/python ]]; then
  echo "Creating .docs-venv (first time)..." >&2
  "$(dirname "$0")/setup_docs_venv.sh"
fi
if ! command -v pandoc >/dev/null 2>&1; then
  echo "Install pandoc: sudo apt install pandoc" >&2
  exit 1
fi
.docs-venv/bin/python scripts/build_docs_pdf.py "$@"
