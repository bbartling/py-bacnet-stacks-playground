#!/usr/bin/env python3
"""Pack a turnkey PythonAnywhere zip (Flask + models + optional WebGL).

Hard guard: refuse zips over 100 MiB unless --force (PA Files-page HTTP upload cap).
"""

from __future__ import annotations

import argparse
import shutil
import sys
import zipfile
from pathlib import Path

_VIBE21 = Path(__file__).resolve().parents[1]
_MAX_MIB = 100
_MAX_BYTES = _MAX_MIB * 1024 * 1024

# Paths relative to vibe21 root included in the zip
_INCLUDE = [
    "flask_app/__init__.py",
    "flask_app/__main__.py",
    "flask_app/app.py",
    "flask_app/model_loader.py",
    "flask_app/predict.py",
    "flask_app/requirements.txt",
    "flask_app/models",
    "flask_app/webgl",
    "flask_app/static",
    "flask_app/tests",
    "ml/__init__.py",
    "ml/artifact_paths.py",
    "ml/feature_compile_dm.py",
    "ml/notebook_plots.py",
    "ml/train_demand_hourly.py",
    "ml/tune_demand_hourly.py",
    "pythonanywhere_mirror/flask_app.py",
    "pythonanywhere_mirror/README.md",
    "notebooks/demand_hourly_training_walkthrough.ipynb",
]


def _should_skip(path: Path) -> bool:
    parts = set(path.parts)
    if "__pycache__" in parts or path.suffix == ".pyc":
        return True
    if path.name == ".gitkeep":
        return False
    return False


def collect_files(root: Path) -> list[tuple[Path, str]]:
    """Return (absolute_path, archive_name) pairs."""
    out: list[tuple[Path, str]] = []
    for rel in _INCLUDE:
        p = root / rel
        if not p.exists():
            continue
        if p.is_file():
            out.append((p, rel.replace("\\", "/")))
            continue
        for f in p.rglob("*"):
            if not f.is_file() or _should_skip(f):
                continue
            arc = f.relative_to(root).as_posix()
            out.append((f, arc))
    # Top-level PA readme
    readme = root / "dist" / "README_PA.md"
    if readme.is_file():
        out.append((readme, "README_PA.md"))
    return out


def write_readme_pa(root: Path) -> Path:
    dist = root / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    text = """# Vibe21 PA turnkey bundle

## Upload limit

PythonAnywhere **Files page / HTTP upload hard cap = 100 MiB**.
If this zip is larger, use SFTP/SCP or split — do not rely on the orange upload button.

## Deploy

1. Upload `vibe21_pa_bundle.zip` (must be ≤100 MiB for Files upload).
2. Bash: `unzip vibe21_pa_bundle.zip -d vibe21_dm_twin && cd vibe21_dm_twin`
3. Web tab WSGI (example):

```python
import sys
path = "/home/YOURUSER/vibe21_dm_twin"
if path not in sys.path:
    sys.path.insert(0, path)
from flask_app.app import create_app
application = create_app()
```

Or use flat `pythonanywhere_mirror/flask_app.py` as `flask_app.py` at the app root.

4. Install deps from `flask_app/requirements.txt` into the web-app virtualenv.
5. **Reload** the web app.

## Smoke

- `GET /api/v1/health` — green when `flask_app/models/demand_hourly_v1.joblib` loads
- `POST /api/v1/predict/demand_hourly` — DR knobs → facility_kw
- `GET /notebooks/demand_hourly` — read-only training notebook HTML
- `GET /` — WebGL if `flask_app/webgl/index.html` present, else API stub JSON

Models are already under `flask_app/models/` (agent/CLI/notebook dump default).
"""
    path = dist / "README_PA.md"
    path.write_text(text, encoding="utf-8")
    return path


def pack(root: Path, out_zip: Path, *, force: bool = False) -> Path:
    write_readme_pa(root)
    files = collect_files(root)
    if not files:
        raise SystemExit("nothing to pack")
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    if out_zip.is_file():
        out_zip.unlink()
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for abs_path, arc in files:
            zf.write(abs_path, arcname=arc)
    size = out_zip.stat().st_size
    mib = size / (1024 * 1024)
    print(f"wrote {out_zip} ({mib:.2f} MiB, {len(files)} files)")
    if size > _MAX_BYTES and not force:
        out_zip.unlink(missing_ok=True)
        raise SystemExit(
            f"ERROR: zip {mib:.2f} MiB exceeds PythonAnywhere Files upload cap "
            f"({_MAX_MIB} MiB). Omit WebGL, use SFTP, or pass --force."
        )
    if size > _MAX_BYTES and force:
        print(f"WARNING: over {_MAX_MIB} MiB but --force set", file=sys.stderr)
    return out_zip


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=_VIBE21)
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Default: <root>/dist/vibe21_pa_bundle.zip",
    )
    ap.add_argument("--force", action="store_true", help="Allow zip > 100 MiB")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    root = args.root.resolve()
    out = args.out or (root / "dist" / "vibe21_pa_bundle.zip")
    if args.dry_run:
        write_readme_pa(root)
        files = collect_files(root)
        total = sum(p.stat().st_size for p, _ in files)
        print(f"would pack {len(files)} files, uncompressed ~{total/1024/1024:.2f} MiB")
        for _, arc in files[:30]:
            print(" ", arc)
        if len(files) > 30:
            print(f"  … +{len(files)-30} more")
        return 0
    pack(root, out, force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
