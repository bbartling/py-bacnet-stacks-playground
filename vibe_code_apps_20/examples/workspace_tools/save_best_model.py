#!/usr/bin/env python3
"""Snapshot a published Twin run as a durable "best model" (IDF + parameters).

Writes under ``uploads/prototypes/best/<label>/``:
  model.idf
  parameters.json   # knobs, bills, weather, G14, hypothesis, source run
  g14_score.json / calibration_scorecard.json (copies when present)

Also updates ``uploads/prototypes/best/CURRENT.json`` when ``--set-current``.

Example::

  docker exec vibe20 python /data/tools/save_best_model.py \\
    --run-id geo_b100_6fl_gas_reheat_r4 \\
    --label b100_preferred \\
    --set-current \\
    --note "Best |gas NMBE| among elec CV<=20; gas CV still ~41%"
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _find_patch_meta(run_id: str, workspace: Path) -> dict[str, Any] | None:
    candidates = [
        workspace / ".artifacts" / "geo_b100_6fl_glass" / f"{run_id}_meta.json",
        workspace / ".artifacts" / "stacked_6floor" / f"{run_id}_meta.json",
        workspace / ".artifacts" / "stacked_6floor" / f"{run_id.replace('_r1', '')}_meta.json",
    ]
    # fuzzy: any *run_id*_meta.json under .artifacts
    for art in (workspace / ".artifacts").glob(f"**/{run_id}_meta.json"):
        candidates.append(art)
    for p in candidates:
        data = _load(p)
        if isinstance(data, dict):
            data = dict(data)
            data["_meta_path"] = str(p)
            return data
    return None


def save_best(
    *,
    workspace: Path,
    run_id: str,
    label: str,
    note: str = "",
    set_current: bool = False,
    role: str = "preferred",
) -> Path:
    run_dir = workspace / "runs" / run_id
    if not run_dir.is_dir():
        raise SystemExit(f"run dir not found: {run_dir}")

    idf = run_dir / "model.idf"
    if not idf.is_file():
        # fall back to uploads/prototypes
        alt = workspace / "uploads" / "prototypes" / f"{run_id}.idf"
        if alt.is_file():
            idf = alt
        else:
            raise SystemExit(f"no model.idf for {run_id}")

    dest = workspace / "uploads" / "prototypes" / "best" / label
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(idf, dest / "model.idf")

    for name in (
        "g14_score.json",
        "calibration_scorecard.json",
        "scorecard.json",
        "run_manifest.json",
        "wattlab_report.json",
    ):
        src = run_dir / name
        if src.is_file():
            shutil.copy2(src, dest / name)

    man = _load(run_dir / "run_manifest.json") or {}
    g14 = _load(run_dir / "g14_score.json") or {}
    patch = _find_patch_meta(run_id, workspace) or {}

    # dial baseline knobs (when meta is a reheat patch on dial_r4)
    dial = _load(workspace / ".artifacts" / "geo_b100_6fl_glass" / "dial_r4_meta.json") or {}

    params: dict[str, Any] = {
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "label": label,
        "role": role,
        "note": note,
        "source_run_id": run_id,
        "source_run_dir": str(run_dir),
        "idf": str(dest / "model.idf"),
        "hypothesis": man.get("hypothesis") or patch.get("hypothesis") or "",
        "weather_epw": man.get("weather")
        or "/data/.artifacts/calibrate_20260723T002036Z/amy.epw",
        "bills_hint": {
            "b100": "/data/reports/utility_bills_b100_area_weighted.csv",
            "b50": "/data/reports/utility_bills_b50_area_weighted.csv",
        },
        "area_ft2": 140_000.0,
        "g14": {
            "elec_pass": g14.get("elec_pass"),
            "gas_pass": g14.get("gas_pass"),
            "g14_pass": g14.get("g14_pass"),
            "elec": g14.get("elec"),
            "gas": g14.get("gas"),
            "annual_elec_delta_pct": g14.get("annual_elec_delta_pct"),
            "annual_gas_delta_pct": g14.get("annual_gas_delta_pct"),
        },
        "baseline_dial_r4": dial or None,
        "patch_parameters": {
            k: patch[k]
            for k in (
                "src",
                "sat_mode",
                "sat_c",
                "sat_winter_c",
                "sat_summer_c",
                "window_u",
                "window_shgc",
                "infil_mult",
                "hw_loop_c",
                "insulation_cond_mult",
                "oa_per_person_mult",
                "winter_oa_earlier",
                "lights_w_per_m2",
                "equip_w_per_m2",
            )
            if k in patch
        }
        or None,
        "patch_meta_full": patch or None,
        "how_to_reuse": [
            f"cp {dest / 'model.idf'} /data/uploads/prototypes/<new_name>.idf",
            "Re-sim: wattlab / run_energyplus with amy.epw + matching bills CSV",
            "Re-apply knobs: python /data/tools/patch_reheat_envelope.py --help "
            "(values in patch_parameters)",
            "Re-publish: include calibration_scorecard.json via write_calibration_scorecard.py",
        ],
    }
    (dest / "parameters.json").write_text(json.dumps(params, indent=2) + "\n", encoding="utf-8")

    readme = dest / "README.md"
    readme.write_text(
        f"# Best model: `{label}`\n\n"
        f"- **Source run:** `{run_id}`\n"
        f"- **Role:** {role}\n"
        f"- **Saved:** {params['saved_at']}\n"
        f"- **Note:** {note or '(none)'}\n\n"
        f"## Files\n\n"
        f"- `model.idf` — frozen EnergyPlus model\n"
        f"- `parameters.json` — knobs, G14, weather/bills, how to reuse\n"
        f"- `g14_score.json` / `calibration_scorecard.json` — score snapshot\n\n"
        f"## Hypothesis\n\n{params['hypothesis']}\n",
        encoding="utf-8",
    )

    if set_current:
        current = {
            "label": label,
            "role": role,
            "path": str(dest),
            "idf": str(dest / "model.idf"),
            "parameters": str(dest / "parameters.json"),
            "source_run_id": run_id,
            "updated_at": params["saved_at"],
            "note": note,
        }
        root = workspace / "uploads" / "prototypes" / "best"
        root.mkdir(parents=True, exist_ok=True)
        (root / "CURRENT.json").write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
        # convenience symlink for quick open
        link = root / "CURRENT.idf"
        if link.is_symlink() or link.exists():
            link.unlink()
        try:
            link.symlink_to(Path(label) / "model.idf")
        except OSError:
            shutil.copy2(dest / "model.idf", link)

    print(json.dumps({"ok": True, "dest": str(dest), "set_current": set_current}, indent=2))
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workspace", default="/data")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--label", required=True, help="Folder name under prototypes/best/")
    ap.add_argument("--note", default="")
    ap.add_argument("--role", default="preferred", help="preferred | baseline | stacked_b50 | …")
    ap.add_argument("--set-current", action="store_true", help="Point CURRENT.json at this snapshot")
    args = ap.parse_args()
    save_best(
        workspace=Path(args.workspace),
        run_id=args.run_id,
        label=args.label,
        note=args.note,
        set_current=args.set_current,
        role=args.role,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
