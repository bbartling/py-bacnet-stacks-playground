#!/usr/bin/env python3
"""Build a sanitized, portable read-only dashboard package for Drive / cloud deploy."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import generate_dashboard as gd
from dashboard_params import PAGE_IDS, PAGE_TITLES, apply_to_generate_dashboard, load_session, validate_params, write_defaults_file

ROOT = Path(__file__).resolve().parent
DEFAULT_OUT = ROOT / "client_package"
DEFAULT_ZIP = ROOT / "building100_dashboard_readonly.zip"

HTML_PAGES = [f"{p}.html" for p in PAGE_IDS]

# Client-facing CSV exports (pre-computed summaries — no raw BAS history).
CSV_EXPORTS = [
    "zone_comfort_by_season.csv",
    "floor_comfort_by_season.csv",
    "mech_cooling_oat_bins_open_meteo.csv",
    "open_meteo_free_cool_daily.csv",
    "economizer_diagnostics_summary_all.csv",
    "economizer_diagnostics_summary_ahu_1.csv",
    "economizer_diagnostics_summary_ahu_2.csv",
    "sensor_limits_reference.csv",
    "ahu_fault_summary_by_season.csv",
    "weather_bas_vs_open_meteo_fault_summary.csv",
    "central_plant_fault_summary_by_season.csv",
]

DOCS_FOR_CLIENT = [
    "docs/ECONOMIZER_FDD_OPERATOR_GUIDE.md",
    "docs/SENSOR_QA_REFERENCE.md",
]

# Never ship dev / analyst tooling in the client bundle.
EXCLUDE_NAMES = {
    "analyst_session.json",
    "report_summary.json",
    "VALIDATION_CHECK.txt",
    "rule_setup_inventory.csv",
    "requirements-dashboard.txt",
    "dashboard_params.py",
    "package_dashboard.py",
    "generate_dashboard.py",
    "economizer_fdd_engine.py",
    "economizer_diagnostics_page.py",
    "sensor_qa_engine.py",
    "economizer_point_mapping.json",
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sanitize_html(html: str) -> str:
    """Remove analyst tooling and absolute dev paths from HTML."""
    html = re.sub(r'<script[^>]*src="/static/dashboard_tune\.js"[^>]*>\s*</script>\s*', "", html)
    html = re.sub(r"<script>window\.DASHBOARD_PAGE[^<]*</script>\s*", "", html)
    html = re.sub(r'<div class="analyst-panel"[^>]*>.*?</div>\s*(?=<div id="page-content")', "", html, flags=re.DOTALL)
    html = re.sub(r"file:///[^\s\"'<>]+", "", html)
    html = re.sub(r"[A-Za-z]:\\Users\\[^\s\"'<>]+", "", html)
    return html


def _write_serve_scripts(out_dir: Path) -> None:
    (out_dir / "serve.bat").write_text(
        """@echo off
cd /d "%~dp0"
echo Building 100 RCx Dashboard — read-only
echo Open http://localhost:8000/index.html in your browser
echo Press Ctrl+C to stop.
python -m http.server 8000
""",
        encoding="utf-8",
    )
    sh = out_dir / "serve.sh"
    sh.write_text(
        """#!/usr/bin/env sh
cd "$(dirname "$0")"
echo "Building 100 RCx Dashboard — read-only"
echo "Open http://localhost:8000/index.html"
echo "Press Ctrl+C to stop."
python3 -m http.server 8000
""",
        encoding="utf-8",
    )
    try:
        sh.chmod(sh.stat().st_mode | 0o111)
    except OSError:
        pass


def _write_deploy_readme(
    out_dir: Path,
    *,
    package_title: str,
    analyst_name: str,
    generated_at: str,
    notes: dict[str, str],
) -> None:
    notes_block = ""
    for pid, note in notes.items():
        if note.strip():
            notes_block += f"\n### {PAGE_TITLES.get(pid, pid)}\n\n{note.strip()}\n"

    text = f"""# {package_title}

**Read-only dashboard package** — static HTML, no Python source, no raw BAS exports.

| Field | Value |
|-------|-------|
| Prepared by | {analyst_name or "—"} |
| Generated | {generated_at} |
| Package type | Sanitized read-only deliverable |

## Quick start (local)

1. Unzip the entire folder (keep all files together).
2. Double-click **`serve.bat`** (Windows) or run **`./serve.sh`** (Mac/Linux).
3. Open **http://localhost:8000/index.html**

Or manually:

```bash
python -m http.server 8000
```

> **Google Drive note:** Drive preview cannot run Plotly charts reliably. **Download and unzip**, then use `serve.bat` / `serve.sh` above.

## Cloud deploy (read-only)

Upload the **unzipped folder contents** (not the zip) to any static host. All asset paths are relative — no build step required.

| Platform | Steps |
|----------|--------|
| **Netlify** | [app.netlify.com/drop](https://app.netlify.com/drop) — drag the unzipped folder |
| **Cloudflare Pages** | New project → Direct upload → select folder |
| **GitHub Pages** | Push folder to `gh-pages` branch; `.nojekyll` included |
| **Google Cloud Storage** | Create bucket → Enable static website → Upload all files → Set `index.html` as main page |
| **Azure Static Web Apps** | Deploy static content from uploaded folder |
| **AWS S3** | Enable static website hosting on bucket; upload files; optional CloudFront CDN |

After deploy, share the public URL. The dashboard is **view-only** — no tuning controls or backend.

## What's included

- `{len(HTML_PAGES)}` HTML report pages with embedded Plotly charts
- `plotly.min.js` — offline-capable chart library (bundled)
- `analyst_delivery.json` — tuned fault parameters and analyst notes metadata
- `fault_tune_defaults.json` — parameter definitions used for this delivery
- CSV summary exports (pre-computed; no live database)
- Operator reference docs in `docs/`

## What's excluded (sanitized)

- Python generators, FastAPI server, tests, pytest cache
- Raw `BUILDING_100/` BAS history (already baked into charts)
- Analyst session / dev validation files

## Analyst notes
{notes_block if notes_block else "\n_(No per-page notes were added.)_\n"}

## Support

Re-open charts in Chrome or Edge. If pages look blank, confirm you are serving over **http://** (not `file://`) and that `plotly.min.js` is in the same folder as `index.html`.
"""
    (out_dir / "README.md").write_text(text, encoding="utf-8")
    (out_dir / "DEPLOY.md").write_text(text, encoding="utf-8")


def verify_package(out_dir: Path) -> list[str]:
    """Return list of verification errors (empty = OK)."""
    errors: list[str] = []
    if not (out_dir / "index.html").is_file():
        errors.append("Missing index.html")
    if not (out_dir / "plotly.min.js").is_file():
        errors.append("Missing plotly.min.js")
    for page in HTML_PAGES:
        if not (out_dir / page).is_file():
            errors.append(f"Missing {page}")
    for page in HTML_PAGES:
        path = out_dir / page
        if not path.is_file():
            continue
        html = path.read_text(encoding="utf-8")
        if "/static/dashboard_tune" in html:
            errors.append(f"{page} still references analyst tune script")
        if 'src="plotly.min.js"' not in html and "plotly" in html.lower():
            errors.append(f"{page} missing plotly.min.js reference")
    for py in out_dir.rglob("*.py"):
        errors.append(f"Dev file leaked into package: {py.relative_to(out_dir)}")
    if (out_dir / "analyst_session.json").is_file():
        errors.append("analyst_session.json must not be in client package")
    return errors


def build_readonly_package(
    out_dir: Path | None = None,
    zip_path: Path | None = None,
    *,
    params: dict | None = None,
    notes: dict | None = None,
    analyst_name: str = "",
    package_title: str = "Building 100 RCx Dashboard",
    from_session: bool = False,
) -> dict:
    """
    Build sanitized read-only package directory + zip.

    Returns manifest dict with paths and file list.
    """
    out_dir = Path(out_dir or DEFAULT_OUT)
    zip_path = Path(zip_path or DEFAULT_ZIP)

    if from_session:
        session = load_session()
        params = validate_params(session.get("params", {}))
        notes = session.get("notes", {})
        analyst_name = session.get("analyst_name", analyst_name)
        package_title = session.get("package_title", package_title)
    else:
        params = validate_params(params or {})
        notes = notes or {}

    write_defaults_file()
    apply_to_generate_dashboard(gd, params, session.get("site_settings"))
    gd.meta["created"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    generated_at = gd.meta["created"]

    # Ensure plotly bundle exists
    if not (ROOT / "plotly.min.js").is_file():
        import plotly

        src = Path(plotly.__file__).parent / "package_data" / "plotly.min.js"
        shutil.copy(src, ROOT / "plotly.min.js")

    raw = gd.load_raw_data()
    ctx = gd.compute_context(raw)

    from economizer_diagnostics_page import build_page

    build_page(generated_at)

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    (out_dir / "docs").mkdir(exist_ok=True)

    # Regenerate HTML into package dir (non-interactive, notes baked in)
    orig_out = gd.OUT
    gd.OUT = out_dir
    try:
        pages_written = gd.write_all_pages(
            ctx,
            params=params,
            notes=notes,
            analyst_name=analyst_name,
            interactive=False,
        )
        gd.export_csv_summaries(ctx)
    finally:
        gd.OUT = orig_out

    # Sanitize HTML in place
    for page in HTML_PAGES:
        path = out_dir / page
        if path.is_file():
            path.write_text(sanitize_html(path.read_text(encoding="utf-8")), encoding="utf-8")

    # Copy bundled assets
    shutil.copy(ROOT / "plotly.min.js", out_dir / "plotly.min.js")
    shutil.copy(ROOT / "fault_tune_defaults.json", out_dir / "fault_tune_defaults.json")

    # Copy allowlisted CSVs from dashboard output
    for name in CSV_EXPORTS:
        src = ROOT / name
        if src.is_file() and name not in EXCLUDE_NAMES:
            shutil.copy(src, out_dir / name)

    for doc in DOCS_FOR_CLIENT:
        src = ROOT / doc
        if src.is_file():
            shutil.copy(src, out_dir / "docs" / src.name)

    delivery = {
        "package_title": package_title,
        "prepared_by": analyst_name,
        "generated_at": generated_at,
        "package_type": "readonly_static",
        "sanitized": True,
        "tune_params": params,
        "notes_by_page": notes,
        "pages": pages_written,
        "csv_exports": [n for n in CSV_EXPORTS if (out_dir / n).is_file()],
    }
    (out_dir / "analyst_delivery.json").write_text(json.dumps(delivery, indent=2), encoding="utf-8")

    _write_serve_scripts(out_dir)
    _write_deploy_readme(
        out_dir,
        package_title=package_title,
        analyst_name=analyst_name,
        generated_at=generated_at,
        notes=notes,
    )
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")

    # Build manifest with checksums
    files: list[dict] = []
    for f in sorted(out_dir.rglob("*")):
        if f.is_file():
            rel = str(f.relative_to(out_dir)).replace("\\", "/")
            if f.name in EXCLUDE_NAMES:
                continue
            files.append({"path": rel, "bytes": f.stat().st_size, "sha256": _sha256(f)})

    manifest = {
        "schema_version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        **delivery,
        "files": files,
        "verify_errors": verify_package(out_dir),
    }
    (out_dir / "package_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    if verify_package(out_dir):
        raise RuntimeError("Package verification failed: " + "; ".join(verify_package(out_dir)))

    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in out_dir.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(out_dir))

    return {
        "ok": True,
        "out_dir": str(out_dir),
        "zip_path": str(zip_path),
        "pages": pages_written,
        "file_count": len(files),
        "manifest": manifest,
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Build sanitized read-only dashboard package")
    parser.add_argument("--from-session", action="store_true", help="Use analyst_session.json tuning + notes")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT, help="Output folder")
    parser.add_argument("--zip", type=Path, default=DEFAULT_ZIP, help="Output zip path")
    args = parser.parse_args()

    result = build_readonly_package(args.output, args.zip, from_session=args.from_session)
    print(f"Package OK: {result['file_count']} files")
    print(f"Folder: {result['out_dir']}")
    print(f"Zip:    {result['zip_path']}")
    print("Upload the zip to Google Drive, or deploy the unzipped folder to any static host (see DEPLOY.md).")


if __name__ == "__main__":
    main()
