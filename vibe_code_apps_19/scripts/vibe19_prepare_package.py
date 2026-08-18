"""Build a flat openfdd_package_v1 zip from a building folder (no LLM).

Usage (from vibe_code_apps_19):
  python scripts/vibe19_prepare_package.py --src path/to/BUILDING_100 --out building.zip
  python scripts/vibe19_prepare_package.py --src path/to/BUILDING_100 --mapping-prompt
  python scripts/vibe19_prepare_package.py --src path/to/BUILDING_100 --out out.zip --split-mb 140
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.column_map_json import (  # noqa: E402
    build_column_map_from_equipment_frames,
    build_llm_prompt_for_frames,
    column_map_to_role_map,
)
from app.data_loader import discover_equipment  # noqa: E402
from app.fdd_runtime import make_session_config  # noqa: E402
from app.package_io import (  # noqa: E402
    BROWSER_UPLOAD_MB,
    PackageManifest,
    SessionConfig,
    load_package_from_dir,
)
from app.site_model import equipment_type_from_id  # noqa: E402


def _frames_from_headers(building: Path) -> dict:
    import pandas as pd

    frames = {}
    for eq in discover_equipment(building):
        hist = Path(eq["history_path"])
        header = pd.read_csv(hist, nrows=0)
        df = pd.DataFrame(columns=list(header.columns))
        df.attrs["equipment_id"] = eq["equipment_id"]
        df.attrs["columns_path"] = str(eq.get("columns_path") or "")
        df.attrs["equipment_type"] = equipment_type_from_id(eq["equipment_id"])
        frames[eq["equipment_id"]] = df
    return frames


def _write_zip(src: Path, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(src.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() == ".zip":
                raise SystemExit(f"Refusing to pack nested zip: {path}")
            zf.write(path, arcname=path.relative_to(src).as_posix())


def _split_zip(src: Path, out: Path, split_mb: int) -> list[Path]:
    limit = int(split_mb) * 1024 * 1024
    parts: list[Path] = []
    part_idx = 1
    current: list[tuple[Path, str]] = []
    current_size = 0

    def flush() -> None:
        nonlocal part_idx, current, current_size
        if not current:
            return
        dest = out.with_name(f"{out.stem}_part{part_idx:02d}.zip")
        with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path, arc in current:
                zf.write(path, arcname=arc)
        parts.append(dest)
        part_idx += 1
        current = []
        current_size = 0

    shared = []
    equipment_groups: dict[str, list[tuple[Path, str]]] = {}
    for path in sorted(src.rglob("*")):
        if not path.is_file():
            continue
        arc = path.relative_to(src).as_posix()
        if arc.split("/")[0] in {"weather"} or path.name in {
            "manifest.json",
            "session_config.json",
            "column_map.json",
            "role_map.yaml",
            "job_manifest.json",
        }:
            shared.append((path, arc))
            continue
        eq = arc.split("/")[0]
        equipment_groups.setdefault(eq, []).append((path, arc))

    # Manifest-bearing first part
    current.extend(shared)
    current_size = sum(p.stat().st_size for p, _ in shared)
    for _eq, files in equipment_groups.items():
        group_size = sum(p.stat().st_size for p, _ in files)
        if current and current_size + group_size > limit:
            flush()
        current.extend(files)
        current_size += group_size
        if current_size >= limit:
            flush()
    flush()
    job = {
        "schema_version": "openfdd_job_v1",
        "parts": [p.name for p in parts],
        "notes": f"Split for Streamlit multi-upload (≤{split_mb} MB target)",
    }
    print(json.dumps(job, indent=2))
    return parts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", type=Path, required=True, help="Building folder with manifest + equipment CSVs")
    ap.add_argument("--out", type=Path, help="Output zip path")
    ap.add_argument("--generate-maps", action="store_true", help="Write column_map.json + session_config.json")
    ap.add_argument("--validate", action="store_true", default=True)
    ap.add_argument("--no-validate", action="store_false", dest="validate")
    ap.add_argument("--mapping-prompt", action="store_true", help="Print mapping helper text (never calls an LLM)")
    ap.add_argument("--mapping-prompt-out", type=Path, help="Write mapping helper text to a file")
    ap.add_argument(
        "--split-mb",
        type=int,
        default=0,
        help=f"If set, write sibling part zips targeting this size (browser cap is {BROWSER_UPLOAD_MB} MB)",
    )
    args = ap.parse_args()
    src = args.src.expanduser().resolve()
    if not src.is_dir():
        raise SystemExit(f"Not a directory: {src}")

    if args.generate_maps:
        frames = _frames_from_headers(src)
        building_id = src.name
        mp = src / "manifest.json"
        if mp.is_file():
            raw = json.loads(mp.read_text(encoding="utf-8"))
            PackageManifest.model_validate(
                {
                    "schema_version": raw.get("schema_version") or "openfdd_package_v1",
                    "building_id": raw.get("building_id") or building_id,
                    "grid_minutes": raw.get("grid_minutes") or 5,
                    "timezone": raw.get("timezone") or "UTC",
                }
            )
            building_id = str(raw.get("building_id") or building_id)
        cmap = build_column_map_from_equipment_frames(frames, building_id=building_id)
        (src / "column_map.json").write_text(json.dumps(cmap, indent=2) + "\n", encoding="utf-8")
        session = make_session_config(column_map_to_role_map(cmap), {})
        SessionConfig.model_validate(session)
        (src / "session_config.json").write_text(json.dumps(session, indent=2) + "\n", encoding="utf-8")
        print("wrote column_map.json + session_config.json")

    if args.mapping_prompt or args.mapping_prompt_out:
        from app.data_loader import load_building_folder as load_frames

        try:
            frames = load_frames(src)
        except Exception:
            frames = _frames_from_headers(src)
        prompt = build_llm_prompt_for_frames(frames, building_id=src.name)
        if args.mapping_prompt_out:
            args.mapping_prompt_out.write_text(prompt, encoding="utf-8")
            print(f"wrote {args.mapping_prompt_out}")
        if args.mapping_prompt:
            print(prompt)

    if args.validate:
        result = load_package_from_dir(src)
        print(
            f"validated {result.manifest.building_id}: "
            f"{len(result.frames)} equipment, weather={result.weather is not None}"
        )

    if args.out:
        if args.split_mb:
            written = _split_zip(src, args.out, args.split_mb)
            for p in written:
                print("wrote", p)
        else:
            _write_zip(src, args.out)
            print(f"wrote {args.out} ({args.out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
