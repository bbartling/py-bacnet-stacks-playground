# Vibe12 documentation PDF

Pre-built manual (when present): **[vibe12-edge-fdd-guide.pdf](vibe12-edge-fdd-guide.pdf)**

## Build locally

```bash
cd vibe_code_apps_12
pip install pyyaml weasyprint
sudo apt install pandoc   # if needed
python3 scripts/build_docs_pdf.py
```

Also writes `pdf/vibe12-edge-fdd-guide.txt` (plain Markdown bundle).

Commit the PDF to GitHub for offline reading:

```bash
git add pdf/vibe12-edge-fdd-guide.pdf pdf/vibe12-edge-fdd-guide.txt
git commit -m "Refresh Vibe12 documentation PDF"
```

Source chapters live in [`docs/`](../docs/) (see [`docs/manifest.yaml`](../docs/manifest.yaml)).
