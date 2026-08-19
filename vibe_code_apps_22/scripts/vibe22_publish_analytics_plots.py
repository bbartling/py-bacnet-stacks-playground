#!/usr/bin/env python3
"""Publish curated analytics PNGs into the Phase 0 publication directory.

Render-only source (practice pack) -> curated git repo figures.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from eplus_native.hashes import sha256_file  # noqa: E402


def _stable_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_text(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def _copy_file(*, src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        # Fail closed if bytes already exist but differ.
        if sha256_file(dst) != sha256_file(src):
            raise ValueError(f"refusing to overwrite mismatched stale file: {dst}")
        return
    dst.write_bytes(src.read_bytes())


def _copy_gl14_latest_best_pngs(*, source_root: Path, dest_analytics_dir: Path) -> list[dict]:
    src_analytics = source_root / "plots" / "analytics"
    if not src_analytics.is_dir():
        raise FileNotFoundError(f"missing source analytics dir: {src_analytics}")

    # Curated allowlist produced by archive eplus_calibration_plots.py (GL14 "latest best").
    top_pngs = [
        "gl14_progress_by_iteration.png",
        "gl14_status_by_iteration.png",
        "monthly_kwh_model_vs_obs_best.png",
        "monthly_fuel_pct_model_vs_actual_best.png",
        "monthly_fuel_share_pct_best.png",
        "monthly_panels_actual_vs_model_best.png",
        "monthly_peak_kw_model_vs_obs_best.png",
        "monthly_error_heatmap.png",
    ]

    records: list[dict] = []

    for fn in top_pngs:
        src = src_analytics / fn
        if not src.is_file():
            raise FileNotFoundError(f"required analytics png missing: {src}")
        rel = Path("plots/analytics") / fn
        dst = dest_analytics_dir / fn
        _copy_file(src=src, dst=dst)
        records.append(
            {
                "rel_path": rel.as_posix(),
                "sha256": sha256_file(src),
                "bytes": src.stat().st_size,
            }
        )

    by_month = src_analytics / "by_month"
    if by_month.is_dir():
        for src in sorted(by_month.glob("fuel_*_actual_vs_model.png")):
            rel = Path("plots/analytics/by_month") / src.name
            dst = dest_analytics_dir / "by_month" / src.name
            _copy_file(src=src, dst=dst)
            records.append(
                {
                    "rel_path": rel.as_posix(),
                    "sha256": sha256_file(src),
                    "bytes": src.stat().st_size,
                }
            )

    return records


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--source-root",
        type=Path,
        default=None,
        help="Practice pack root (sp_creekside). Default: $SITE_ROOT.",
    )
    ap.add_argument(
        "--dest-figure-root",
        type=Path,
        default=Path("vibe_code_apps_22/docs/audits/figures/vibe22_final_physics_control_strategy_comparison"),
        help="Where to publish figures under docs/audits/figures.",
    )
    args = ap.parse_args(argv)

    site_root = args.source_root or Path.cwd()  # default; next block fixes it
    # Resolve default from environment if not passed.
    import os

    env = os.environ.get("SITE_ROOT") or os.environ.get("LAKESIDE_SITE_ROOT") or os.environ.get("VIBE22_SITE_ROOT")
    if args.source_root is None and env:
        site_root = Path(env)

    if not site_root.is_dir():
        raise SystemExit(f"missing --source-root or env SITE_ROOT/LAKESIDE_SITE_ROOT; got: {site_root}")

    dest_analytics_dir = args.dest_figure_root / "plots" / "analytics"
    dest_analytics_dir.mkdir(parents=True, exist_ok=True)

    records = _copy_gl14_latest_best_pngs(
        source_root=site_root,
        dest_analytics_dir=dest_analytics_dir,
    )

    # Deterministic (timestamp-free) provenance manifest for what we committed.
    body = {
        "schema": "vibe22.phase0.analytics_source_manifest.v1",
        "claim_label": "vibe22_final_physics_control_strategy_comparison",
        "source_root_label": "SITE_ROOT",
        "files": records,
    }
    body["files_sha256"] = _sha256_text(_stable_json(body["files"]))

    out = dest_analytics_dir / "source_manifest.json"
    out.write_text(_stable_json(body) + "\n", encoding="utf-8")
    print(f"published {len(records)} png(s) -> {dest_analytics_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

