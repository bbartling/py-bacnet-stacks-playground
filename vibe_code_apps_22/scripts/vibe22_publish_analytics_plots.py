#!/usr/bin/env python3
"""Publish curated sp_creekside plot artifacts into the git repo.

Render-only source (practice pack SITE_ROOT) -> curated figures under
``docs/audits/figures/vibe22_final_physics_control_strategy_comparison/``.

Sections:
  - IdealLoads GL14 calibration analytics (``plots/analytics/``)
  - W2A dial GL14 vs peak285 campaign (``plots/analytics/eplus_gl14_vs_peak285/``)
  - Site demand / zone diagnostics PNGs
  - Zone heat-pump trend PNGs (``plots/HP*.png``)
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

DEFAULT_FIGURE_ROOT = (
    _APP / "docs" / "audits" / "figures" / "vibe22_final_physics_control_strategy_comparison"
)

GL14_CALIBRATION_PNGS = [
    "gl14_progress_by_iteration.png",
    "gl14_status_by_iteration.png",
    "monthly_kwh_model_vs_obs_best.png",
    "monthly_fuel_pct_model_vs_actual_best.png",
    "monthly_fuel_share_pct_best.png",
    "monthly_panels_actual_vs_model_best.png",
    "monthly_peak_kw_model_vs_obs_best.png",
    "monthly_error_heatmap.png",
]

SITE_ANALYTICS_PNGS = [
    "demand_monthly_weekday_weekend_profiles.png",
    "demand_vs_web_weather_density.png",
    "demand_vs_web_weather_scatter.png",
    "demand_vs_web_weather_scatter_peak_day.png",
    "demand_weekday_weekend_summary.png",
    "zone_avg_fan_run_hours_by_month.png",
    "zone_temp_occ_unocc_by_month.png",
]

W2A_DIAL_PNGS = [
    "pareto_gl14_vs_peak.png",
    "monthly_gl14_c02_l22_pk285.png",
    "monthly_gl14_kwh_c02_pk285.png",
    "monthly_kwh_line_a04_ladder.png",
    "monthly_kwh_line_all_models.png",
    "monthly_kwh_line_soft_cop.png",
    "peak_day_actual_c02_pk285.png",
    "peak_day_actual_c02_pk285_l22.png",
    "peak_day_actual_c02_pk285_l22_e20.png",
    "peak_day_e20_sc02_r02_a04.png",
    "peak_day_enduse_stack_A04.png",
    "peak_day_enduse_stack_E20.png",
    "peak_day_enduse_stack_L22.png",
    "peak_day_enduse_stack_SC02.png",
    "peak_day_soft_cop_e20_sc.png",
    "winter_wd_we_profiles_a04_ladder.png",
    "winter_wd_we_profiles_all_models.png",
    "winter_wd_we_profiles_soft_cop.png",
    "winter_weekday_profiles_c02_pk285_l22_e20.png",
    "gl14_gate_scatter_enhanced.png",
    "gl14_peak_pareto_enhanced.png",
    "enhanced_dial_trials_gl14.png",
]

W2A_DIAL_DATA = [
    "a04_dial_scorecard.csv",
    "enhanced_dial_trials.csv",
    "soft_cop_scorecard.csv",
    "soft_cop_trials.csv",
    "monthly_gl14_both_models.csv",
    "enhanced_gl14_payload.json",
]


def _stable_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_text(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def _copy_with_rel(*, src: Path, dst: Path, rel_path: Path, overwrite: bool) -> dict | None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        if sha256_file(dst) == sha256_file(src):
            return {
                "rel_path": rel_path.as_posix(),
                "sha256": sha256_file(src),
                "bytes": src.stat().st_size,
                "status": "UNCHANGED",
            }
        if not overwrite:
            raise ValueError(f"refusing to overwrite mismatched stale file: {dst}")
    dst.write_bytes(src.read_bytes())
    return {
        "rel_path": rel_path.as_posix(),
        "sha256": sha256_file(dst),
        "bytes": dst.stat().st_size,
        "status": "COPIED",
    }


def _copy_named_files(
    *,
    src_dir: Path,
    dst_dir: Path,
    rel_prefix: Path,
    names: list[str],
    overwrite: bool,
    required: bool,
) -> list[dict]:
    records: list[dict] = []
    for fn in names:
        src = src_dir / fn
        if not src.is_file():
            if required:
                raise FileNotFoundError(f"required file missing: {src}")
            continue
        rel = rel_prefix / fn
        dst = dst_dir / fn
        rec = _copy_with_rel(src=src, dst=dst, rel_path=rel, overwrite=overwrite)
        if rec:
            records.append(rec)
    return records


def _copy_glob(
    *,
    src_dir: Path,
    dst_dir: Path,
    rel_prefix: Path,
    pattern: str,
    overwrite: bool,
) -> list[dict]:
    records: list[dict] = []
    for src in sorted(src_dir.glob(pattern)):
        rel = rel_prefix / src.name
        dst = dst_dir / src.name
        rec = _copy_with_rel(src=src, dst=dst, rel_path=rel, overwrite=overwrite)
        if rec:
            records.append(rec)
    return records


def publish_all(
    *,
    source_root: Path,
    dest_figure_root: Path,
    overwrite: bool = False,
) -> tuple[list[dict], Path]:
    src_plots = source_root / "plots"
    if not src_plots.is_dir():
        raise FileNotFoundError(f"missing plots dir: {src_plots}")

    dest_root = dest_figure_root
    records: list[dict] = []

    # IdealLoads GL14 calibration
    src_analytics = src_plots / "analytics"
    dest_analytics = dest_root / "plots" / "analytics"
    records.extend(
        _copy_named_files(
            src_dir=src_analytics,
            dst_dir=dest_analytics,
            rel_prefix=Path("plots/analytics"),
            names=GL14_CALIBRATION_PNGS,
            overwrite=overwrite,
            required=True,
        )
    )
    records.extend(
        _copy_glob(
            src_dir=src_analytics / "by_month",
            dst_dir=dest_analytics / "by_month",
            rel_prefix=Path("plots/analytics/by_month"),
            pattern="fuel_*_actual_vs_model.png",
            overwrite=overwrite,
        )
    )

    # Site demand / zone analytics
    records.extend(
        _copy_named_files(
            src_dir=src_analytics,
            dst_dir=dest_analytics,
            rel_prefix=Path("plots/analytics"),
            names=SITE_ANALYTICS_PNGS,
            overwrite=overwrite,
            required=False,
        )
    )

    # W2A dial GL14 vs peak285
    src_w2a = src_analytics / "eplus_gl14_vs_peak285"
    dest_w2a = dest_analytics / "eplus_gl14_vs_peak285"
    records.extend(
        _copy_named_files(
            src_dir=src_w2a,
            dst_dir=dest_w2a,
            rel_prefix=Path("plots/analytics/eplus_gl14_vs_peak285"),
            names=W2A_DIAL_PNGS,
            overwrite=overwrite,
            required=False,
        )
    )
    records.extend(
        _copy_named_files(
            src_dir=src_w2a,
            dst_dir=dest_w2a,
            rel_prefix=Path("plots/analytics/eplus_gl14_vs_peak285"),
            names=W2A_DIAL_DATA,
            overwrite=overwrite,
            required=False,
        )
    )
    # Copy any remaining dial PNGs not in the explicit allowlist (notebook extras).
    if src_w2a.is_dir():
        known = set(W2A_DIAL_PNGS)
        for src in sorted(src_w2a.glob("*.png")):
            if src.name in known:
                continue
            rel = Path("plots/analytics/eplus_gl14_vs_peak285") / src.name
            rec = _copy_with_rel(
                src=src,
                dst=dest_w2a / src.name,
                rel_path=rel,
                overwrite=overwrite,
            )
            if rec:
                records.append(rec)

    # Zone HP + meter trend PNGs at plots root
    dest_hp = dest_root / "plots" / "site_diagnostics"
    for src in sorted(src_plots.glob("*.png")):
        rel = Path("plots/site_diagnostics") / src.name
        rec = _copy_with_rel(
            src=src,
            dst=dest_hp / src.name,
            rel_path=rel,
            overwrite=overwrite,
        )
        if rec:
            records.append(rec)

    # plot_manifest.json (png paths only, sorted)
    png_paths = sorted({r["rel_path"] for r in records if r["rel_path"].endswith(".png")})
    manifest = {
        "schema": "vibe22.phase0.plot_manifest.v1",
        "claim_label": "vibe22_final_physics_control_strategy_comparison",
        "plots": png_paths,
    }
    manifest_path = dest_root / "plot_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    body = {
        "schema": "vibe22.phase0.analytics_source_manifest.v1",
        "claim_label": "vibe22_final_physics_control_strategy_comparison",
        "source_root_label": "SITE_ROOT",
        "files": records,
    }
    body["files_sha256"] = _sha256_text(_stable_json(body["files"]))
    prov_path = dest_analytics / "source_manifest.json"
    prov_path.write_text(_stable_json(body) + "\n", encoding="utf-8")

    return records, prov_path


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source-root", type=Path, default=None)
    ap.add_argument("--dest-figure-root", type=Path, default=DEFAULT_FIGURE_ROOT)
    ap.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace committed figures when SITE_ROOT bytes differ.",
    )
    ap.add_argument(
        "--build-enhanced-gl14",
        action="store_true",
        help="Run w2a dial GL14 chart builder on SITE_ROOT before copy.",
    )
    args = ap.parse_args(argv)

    import os

    site_root = args.source_root
    if site_root is None:
        env = os.environ.get("SITE_ROOT") or os.environ.get("LAKESIDE_SITE_ROOT")
        if env:
            site_root = Path(env)
    if site_root is None or not site_root.is_dir():
        raise SystemExit("missing --source-root or SITE_ROOT")

    if args.build_enhanced_gl14:
        from plots.w2a_dial._build_enhanced_gl14_charts import build_charts

        build_charts(analytics_dir=site_root / "plots/analytics/eplus_gl14_vs_peak285")

    records, prov = publish_all(
        source_root=site_root,
        dest_figure_root=args.dest_figure_root,
        overwrite=args.overwrite,
    )
    n_png = sum(1 for r in records if r["rel_path"].endswith(".png"))
    print(f"published {n_png} png(s), {len(records)} total files -> {args.dest_figure_root}")
    print(f"provenance: {prov}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
