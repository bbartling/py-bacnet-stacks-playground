#!/usr/bin/env bash
# One-time setup for PDF doc builds (avoids PEP 668 system pip errors).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "System packages for WeasyPrint (run once if PDF build fails):" >&2
echo "  sudo apt install -y pandoc libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 shared-mime-info" >&2

python3 -m venv .docs-venv
.docs-venv/bin/pip install -U pip
.docs-venv/bin/pip install -r requirements-docs.txt

if ! .docs-venv/bin/weasyprint --version >/dev/null 2>&1; then
  echo "" >&2
  echo "WeasyPrint installed but system libraries missing (libpango)." >&2
  echo "Run the sudo apt line above, then ./scripts/build_docs.sh again." >&2
  exit 1
fi

echo "OK. Build PDF with:"
echo "  $ROOT/scripts/build_docs.sh"
