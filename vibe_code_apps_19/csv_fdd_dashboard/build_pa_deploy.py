#!/usr/bin/env python3
"""
Build PythonAnywhere deploy zip (Unity WebGL-style workflow).

Local workflow:
  1. Tune charts + notes locally (DASHBOARD_MODE=full, python app.py)
  2. python build_pa_deploy.py --from-session
  3. Upload building100_pa_deploy.zip to PythonAnywhere → extract → configure wsgi.py

The zip contains ONLY what PA needs — no BUILDING_100 raw data, no generator source.
"""

from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

from dashboard_params import load_session
from package_dashboard import build_readonly_package

ROOT = Path(__file__).resolve().parent
SITE_DIR = ROOT / "site"
STAGING = ROOT / "pa_staging"
ZIP_PATH = ROOT / "building100_pa_deploy.zip"

PA_FILES = [
    "app.py",
    "wsgi.py",
    "requirements.txt",
    "PYTHONANYWHERE.md",
]

PA_STATIC = [
    "static/dashboard_notes.js",
]


def build_pa_deploy(*, from_session: bool = True) -> dict:
    # 1. Bake charts into site/ (like Unity WebGL Build/)
    build_readonly_package(
        out_dir=SITE_DIR,
        zip_path=ROOT / "_site_build_temp.zip",
        from_session=from_session,
    )
    temp_zip = ROOT / "_site_build_temp.zip"
    if temp_zip.exists():
        temp_zip.unlink()

    # 2. Seed live notes from analyst session
    notes: dict[str, str] = {}
    analyst_name = ""
    if from_session and (ROOT / "analyst_session.json").is_file():
        session = load_session()
        notes = session.get("notes", {})
        analyst_name = session.get("analyst_name", "")

    data_dir = STAGING / "data"
    if STAGING.exists():
        shutil.rmtree(STAGING)
    STAGING.mkdir()
    data_dir.mkdir()
    (STAGING / "static").mkdir()

    notes_payload = {
        "analyst_name": analyst_name,
        "notes_by_page": notes,
    }
    (data_dir / "analyst_notes.json").write_text(json.dumps(notes_payload, indent=2), encoding="utf-8")

    # 3. Copy site build + Flask runner
    shutil.copytree(SITE_DIR, STAGING / "site")

    for name in PA_FILES:
        src = ROOT / name
        if src.is_file():
            shutil.copy(src, STAGING / name)

    for rel in PA_STATIC:
        src = ROOT / rel
        if src.is_file():
            dest = STAGING / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, dest)

    # 4. Zip
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in STAGING.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(STAGING))

    file_count = sum(1 for _ in STAGING.rglob("*") if _.is_file())
    shutil.rmtree(STAGING)

    return {
        "ok": True,
        "zip_path": str(ZIP_PATH),
        "site_dir": str(SITE_DIR),
        "file_count": file_count,
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Build PythonAnywhere deploy zip")
    parser.add_argument("--from-session", action="store_true", default=True)
    parser.add_argument("--no-session", action="store_true", help="Use default params, no saved notes")
    args = parser.parse_args()
    from_session = not args.no_session

    result = build_pa_deploy(from_session=from_session)
    print(f"PythonAnywhere deploy zip ready: {result['file_count']} files")
    print(f"Site build: {result['site_dir']}")
    print(f"Upload:     {result['zip_path']}")
    print("See PYTHONANYWHERE.md for upload steps.")


if __name__ == "__main__":
    main()
