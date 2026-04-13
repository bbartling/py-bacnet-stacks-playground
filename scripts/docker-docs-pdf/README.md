# Docs PDF (Docker)

Pandoc + WeasyPrint on Debian (same stack as easy-aso CI). Use this when your host is Windows and local PDF generation is awkward.

## One-time image build

From the **playground repo root** (`py-bacnet-stacks-playground`):

```bash
docker build -t py-bacnet-docs-pdf:local -f scripts/docker-docs-pdf/Dockerfile scripts/docker-docs-pdf
```

## Build PDFs (App 7 + App 8)

Still from repo root — mount the repo at `/work`:

**Linux / macOS**

```bash
docker run --rm -v "$(pwd):/work" -w /work py-bacnet-docs-pdf:local bash scripts/docker-docs-pdf/run.sh
```

**PowerShell (Windows)**

```powershell
.\scripts\docker-docs-pdf\Run-DocsPdf.ps1
```

That script builds `documentation.pdf` and `documentation.txt` next to each app (sources: `vibe_code_apps_*/docs/**/*.md`).

## Other apps

Call `scripts/build_docs_pdf.py` yourself inside the same container, for example:

```bash
docker run --rm -v "$(pwd):/work" -w /work py-bacnet-docs-pdf:local \
  python3 scripts/build_docs_pdf.py \
    --docs-dir /work/some_app/docs \
    --title "My bundle" \
    -o /work/some_app/documentation.pdf
```
