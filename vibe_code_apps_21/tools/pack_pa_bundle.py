#!/usr/bin/env python3
"""Pack a turnkey PythonAnywhere zip (Cannon-style mysite layout).

Layout matches CannonPhysicsSim/pythonanywhere_flask:
  flask_app.py   — flat WSGI module (from flask_app import app)
  twin_api/      — Flask package + models (renamed so it cannot clash with flask_app.py)
  webgl/         — Unity WebGL (optional; at mysite root like tank-war)
  ml/            — feature compile helpers for the loader
  requirements.txt

Hard guard: refuse zips over 100 MiB unless --force (PA Files-page HTTP upload cap).
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

_VIBE21 = Path(__file__).resolve().parents[1]
_MAX_MIB = 100
_MAX_BYTES = _MAX_MIB * 1024 * 1024

# Source paths under vibe21 → archive name (mysite-ready)
_PACKAGE_FILES = [
    "flask_app/__init__.py",
    "flask_app/__main__.py",
    "flask_app/app.py",
    "flask_app/model_loader.py",
    "flask_app/predict.py",
    "flask_app/models",
    "flask_app/static",
    "flask_app/tests",
]
_ML_FILES = [
    "ml/__init__.py",
    "ml/artifact_paths.py",
    "ml/feature_compile_dm.py",
    "ml/notebook_plots.py",
    "ml/train_demand_hourly.py",
    "ml/tune_demand_hourly.py",
]


def _should_skip(path: Path) -> bool:
    parts = set(path.parts)
    if "__pycache__" in parts or path.suffix == ".pyc":
        return True
    return False


def _remap_package(rel: str) -> str:
    """flask_app/... → twin_api/... (avoid clash with flat flask_app.py)."""
    rel = rel.replace("\\", "/")
    if rel == "flask_app" or rel.startswith("flask_app/"):
        return "twin_api" + rel[len("flask_app") :]
    return rel


def collect_files(root: Path) -> list[tuple[Path, str]]:
    """Return (absolute_path, archive_name) pairs for mysite extract."""
    out: list[tuple[Path, str]] = []

    # Flat Cannon-style entry + root requirements
    mirror = root / "pythonanywhere_mirror" / "flask_app.py"
    if mirror.is_file():
        out.append((mirror, "flask_app.py"))
    req = root / "flask_app" / "requirements.txt"
    if req.is_file():
        out.append((req, "requirements.txt"))

    for rel in _PACKAGE_FILES + _ML_FILES:
        p = root / rel
        if not p.exists():
            continue
        if p.is_file():
            out.append((p, _remap_package(rel)))
            continue
        for f in p.rglob("*"):
            if not f.is_file() or _should_skip(f):
                continue
            arc_src = f.relative_to(root).as_posix()
            # webgl inside package → also emit at zip-root webgl/ (Cannon)
            if "/webgl/" in arc_src or arc_src.endswith("/webgl"):
                continue
            out.append((f, _remap_package(arc_src)))

    # WebGL at zip root (Cannon: <app>/webgl) — real player required
    webgl = root / "flask_app" / "webgl"
    index = webgl / "index.html"
    if not index.is_file():
        raise SystemExit(
            f"ERROR: missing {index}. Build WebGL first:\n"
            "  powershell -File tools/build_webgl_pa.ps1\n"
            "or Unity menu: Vibe21 → Build WebGL → flask_app/webgl"
        )
    for f in webgl.rglob("*"):
        if not f.is_file() or _should_skip(f):
            continue
        if f.name in (".gitkeep",):
            continue
        rel = f.relative_to(webgl).as_posix()
        out.append((f, f"webgl/{rel}"))

    readme = root / "dist" / "README_PA.md"
    if readme.is_file():
        out.append((readme, "README_PA.md"))

    mirror_readme = root / "pythonanywhere_mirror" / "README.md"
    if mirror_readme.is_file():
        out.append((mirror_readme, "pythonanywhere_mirror/README.md"))

    return out


def write_readme_pa(root: Path) -> Path:
    dist = root / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    text = """# Vibe21 PA turnkey — Cannon / mysite layout

Same shape as `CannonPhysicsSim/pythonanywhere_flask`:
flat `flask_app.py` + `webgl/` + WSGI `from flask_app import app as application`.

## Build (required — zip refuses empty webgl/)

```powershell
cd vibe_code_apps_21
powershell -File tools/build_webgl_pa.ps1
# → dist/vibe21_pa_bundle.zip with webgl/index.html + Build/
```

PythonAnywhere **Files page upload hard cap = 100 MiB**. If larger, use SFTP.

## Deploy (unzip into app root, e.g. `~` or `mysite`)

```bash
cd ~
unzip -o vibe21_pa_bundle.zip
ls webgl/Build
```

### Virtualenv (required)

Bare `pip install` goes to `~/.local` and the Web worker often **cannot** see it.
Use the venv path from the Web tab, e.g.:

```bash
# replace with the path shown under Web → Virtualenv
mkvirtualenv --python=python3.10 vibe21
workon vibe21
pip install -r ~/mysite/requirements.txt
```

Or with the venv pip directly:

```bash
~/.virtualenvs/vibe21/bin/pip install -r ~/mysite/requirements.txt
```

Point the Web tab Virtualenv field at that venv, then **Reload**.

### WSGI (`/var/www/bensapi_pythonanywhere_com_wsgi.py`)

```python
import sys

project_home = "/home/bensApi/mysite"
if project_home not in sys.path:
    sys.path = [project_home] + sys.path

from flask_app import app as application
```

### Static files (match wherever you unzipped)

If zip is in `~` (`/home/bensApi`):

| URL | Directory |
|-----|-----------|
| `/Build/` | `/home/bensApi/webgl/Build` |
| `/TemplateData/` | `/home/bensApi/webgl/TemplateData` |

## Public URL (not the Files browser)

- App: `https://bensapi.pythonanywhere.com/`
- Health: `https://bensapi.pythonanywhere.com/api/v1/health`
- Files UI `pythonanywhere.com/user/.../files/...` is **not** the game/API URL.

## Smoke

- `GET /api/v1/health`
- `POST /api/v1/predict/demand_hourly`
- `GET /` — WebGL if `webgl/index.html` present, else JSON stub

Models: `twin_api/models/` (env set by flat `flask_app.py`).
"""
    path = dist / "README_PA.md"
    path.write_text(text, encoding="utf-8")
    return path


def pack(root: Path, out_zip: Path, *, force: bool = False) -> Path:
    write_readme_pa(root)
    files = collect_files(root)
    if not files:
        raise SystemExit("nothing to pack")
    # Deduplicate archive names (last wins)
    by_arc: dict[str, Path] = {}
    for abs_path, arc in files:
        by_arc[arc] = abs_path
    pairs = list(by_arc.items())
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    if out_zip.is_file():
        out_zip.unlink()
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for arc, abs_path in sorted(pairs):
            zf.write(abs_path, arcname=arc)
    size = out_zip.stat().st_size
    mib = size / (1024 * 1024)
    print(f"wrote {out_zip} ({mib:.2f} MiB, {len(pairs)} files)")
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
        by_arc = {arc: p for p, arc in files}
        total = sum(p.stat().st_size for p in by_arc.values())
        print(f"would pack {len(by_arc)} files, uncompressed ~{total/1024/1024:.2f} MiB")
        for arc in sorted(by_arc)[:40]:
            print(" ", arc)
        if len(by_arc) > 40:
            print(f"  … +{len(by_arc)-40} more")
        return 0
    pack(root, out, force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
