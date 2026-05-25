# Vibe12 documentation PDF

| File | Status |
|------|--------|
| [vibe12-edge-fdd-guide.txt](vibe12-edge-fdd-guide.txt) | Built whenever `build_docs.sh` runs (plain Markdown) |
| [vibe12-edge-fdd-guide.pdf](vibe12-edge-fdd-guide.pdf) | Needs WeasyPrint system libs + venv (below) |

## What happened on your last run?

- **`pip install` failed** — Ubuntu PEP 668 blocks system-wide pip. Use **`.docs-venv`** (not bare `pip`).
- **PDF was not created** — only `.txt` was written; Pandoc could not find WeasyPrint.
- **`git add …pdf` failed** — because no PDF file existed yet.

## Build on bensserver (correct commands)

```bash
cd ~/py-bacnet-stacks-playground && git pull origin develop
cd vibe_code_apps_12

# System: pandoc + WeasyPrint native libraries (once)
sudo apt install -y pandoc libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 shared-mime-info

# Python: venv with weasyprint (once) — do NOT use bare pip install
./scripts/setup_docs_venv.sh

# Build PDF + txt
./scripts/build_docs.sh
ls -lh pdf/vibe12-edge-fdd-guide.pdf
```

## Commit to GitHub

```bash
git add pdf/vibe12-edge-fdd-guide.pdf pdf/vibe12-edge-fdd-guide.txt
git commit -m "Add Vibe12 documentation PDF"
git push origin develop
```

Source chapters: [`docs/`](../docs/) · [`docs/manifest.yaml`](../docs/manifest.yaml)
