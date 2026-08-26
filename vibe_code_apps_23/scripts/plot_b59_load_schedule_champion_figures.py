#!/usr/bin/env python3
"""Publish R22 LOAD_SCHEDULE champion calibration figure pack.

Builds monthly GL14/residual charts, hourly load profiles with percent-difference
shapes, monthly peak kW, and campaign progress. Requires local R22 eplusout.csv.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from vibe23.b59_campaign_runner import parse_hourly_target_proxy
from vibe23.calibration import align_series, peak_check
from vibe23.charts import (
    build_calibration_chart_pack,
    build_extended_monthly_charts,
    build_gl14_campaign_progress,
    build_profile_pct_chart,
)
from vibe23.energyplus import sha256_file

CLAIM_STATUS = "LOAD_SCHEDULE_DIALIN_SCREENING_NOT_CALIBRATED"
TITLE = "B59 R22 load-schedule dial-in champion — LOAD_SCHEDULE_DIALIN_SCREENING_NOT_CALIBRATED"
TIME_BASIS_NOTE = (
    "Measured 15-min office subtotal uses source-clock UTC timestamps; EnergyPlus "
    "hourly output uses local-standard 2020 stamps without DST reconciliation."
)


def _load_measured_15min_kw(path: Path) -> pd.Series:
    frame = pd.read_csv(path)
    timestamps = pd.to_datetime(frame["timestamp"], utc=True, errors="raise")
    values = pd.to_numeric(frame["office_total_kw"], errors="raise")
    series = pd.Series(values.to_numpy(dtype=float), index=pd.DatetimeIndex(timestamps), name="measured_kw")
    if series.index.has_duplicates:
        raise ValueError("measured 15-min CSV contains duplicate timestamps")
    return series.sort_index().tz_localize(None)


def export_hourly_comparison(
    *,
    eplusout_csv: Path,
    measured_15min_csv: Path,
    output_csv: Path,
) -> pd.DataFrame:
    """Pair measured 15-min mean kW with simulated hourly target-proxy kW."""
    measured = _load_measured_15min_kw(measured_15min_csv)
    simulated_j = parse_hourly_target_proxy(eplusout_csv)
    simulated_kw = simulated_j / 3_600_000.0
    simulated_kw.name = "simulated_kw"
    aligned = align_series(measured, simulated_kw, interval="1h", aggregation="mean")
    paired = aligned.paired.rename(columns={"measured": "measured", "simulated": "simulated"})
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    export = paired.reset_index(names="timestamp")
    export["timestamp"] = export["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    export.to_csv(output_csv, index=False)
    return paired


def _monthly_peak_series(hourly: pd.DataFrame) -> pd.Series:
    peaks = hourly["simulated"].groupby(hourly.index.to_period("M")).max()
    index = pd.DatetimeIndex([period.to_timestamp() for period in peaks.index])
    return pd.Series(peaks.to_numpy(dtype=float), index=index, name="simulated_peak_kw")


def _patch_manifest(manifest_path: Path, *, claim_status: str, time_basis_note: str) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["claim_status"] = claim_status
    manifest["time_basis_note"] = time_basis_note
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _measured_peak_series(measured_monthly_csv: Path) -> pd.Series:
    frame = pd.read_csv(measured_monthly_csv)
    months = pd.to_datetime(frame["month"], utc=True, errors="raise").dt.tz_localize(None)
    peaks = pd.to_numeric(frame["peak_kw"], errors="raise")
    return pd.Series(peaks.to_numpy(dtype=float), index=pd.DatetimeIndex(months), name="measured_peak_kw")


def _enrich_campaign_log(campaign_log: Path, measured_monthly: Path) -> Path:
    frame = pd.read_csv(campaign_log)
    if "complete_months" not in frame.columns:
        frame["complete_months"] = 12
    if "target_sha256" not in frame.columns:
        frame["target_sha256"] = sha256_file(measured_monthly)
    enriched = campaign_log.parent / "campaign_log_enriched.csv"
    frame.to_csv(enriched, index=False)
    return enriched


def _append_manifest_artifacts(manifest_path: Path, extra_paths: list[Path]) -> None:
    if not manifest_path.is_file():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    existing = {item["path"] for item in manifest.get("artifacts", [])}
    for path in extra_paths:
        if path.name in existing:
            continue
        manifest["artifacts"].append(
            {
                "path": path.name,
                "sha256": sha256_file(path),
                "media_type": "image/png"
                if path.suffix == ".png"
                else "image/svg+xml"
                if path.suffix == ".svg"
                else "text/csv",
            }
        )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def publish_figures(
    *,
    scorecard_dir: Path,
    run_dir: Path,
    measured_15min: Path,
    measured_monthly: Path,
) -> dict[str, Any]:
    scorecard_dir = Path(scorecard_dir).resolve()
    run_dir = Path(run_dir).resolve()
    eplusout = run_dir / "eplusout.csv"
    if not eplusout.is_file():
        raise FileNotFoundError(
            f"missing {eplusout}; re-run scripts/run_b59_load_schedule_dialin_24.py locally first"
        )

    figures_root = scorecard_dir / "figures"
    monthly_dir = figures_root / "monthly"
    hourly_dir = figures_root / "hourly"
    campaign_dir = figures_root / "campaign"

    champion_monthly = scorecard_dir / "champion_monthly_comparison.csv"
    campaign_log = scorecard_dir / "campaign_log.csv"
    hourly_csv = hourly_dir / "champion_hourly_comparison.csv"

    hourly = export_hourly_comparison(
        eplusout_csv=eplusout,
        measured_15min_csv=measured_15min,
        output_csv=hourly_csv,
    )

    monthly_manifest = build_calibration_chart_pack(
        champion_monthly,
        monthly_dir,
        timestamp_column="timestamp",
        measured_column="measured",
        simulated_column="simulated",
        data_kind="interval_energy",
        energy_unit="kWh",
        title=TITLE,
        parameters=1,
    )
    _patch_manifest(monthly_dir / "chart_manifest.json", claim_status=CLAIM_STATUS, time_basis_note=TIME_BASIS_NOTE)

    monthly_frame = pd.read_csv(champion_monthly, parse_dates=["timestamp"]).set_index("timestamp").sort_index()
    monthly_frame.index = pd.DatetimeIndex(monthly_frame.index).tz_localize(None)
    measured_peaks = _measured_peak_series(measured_monthly)
    simulated_peaks = _monthly_peak_series(hourly)
    extended = build_extended_monthly_charts(
        monthly_frame,
        measured_peak_kw=measured_peaks,
        simulated_peak_kw=simulated_peaks,
        title=TITLE,
        output_dir=monthly_dir,
    )
    _append_manifest_artifacts(monthly_dir / "chart_manifest.json", extended)

    build_calibration_chart_pack(
        hourly_csv,
        hourly_dir,
        timestamp_column="timestamp",
        measured_column="measured",
        simulated_column="simulated",
        data_kind="mean_power",
        unit="kW",
        title=TITLE,
        parameters=1,
    )
    _patch_manifest(hourly_dir / "chart_manifest.json", claim_status=CLAIM_STATUS, time_basis_note=TIME_BASIS_NOTE)
    profile_paths = build_profile_pct_chart(hourly, title=TITLE, output_dir=hourly_dir)
    _append_manifest_artifacts(hourly_dir / "chart_manifest.json", profile_paths)
    hourly_manifest = json.loads((hourly_dir / "chart_manifest.json").read_text(encoding="utf-8"))

    enriched_log = _enrich_campaign_log(campaign_log, measured_monthly)
    campaign_manifest = build_gl14_campaign_progress(
        enriched_log,
        campaign_dir,
        title="B59 load-schedule dial-in 24-run campaign",
    )

    peak = peak_check(hourly["measured"], hourly["simulated"])
    summary = {
        "claim_status": CLAIM_STATUS,
        "figures_root": str(figures_root),
        "monthly_gl14": monthly_manifest.get("monthly_gl14_style"),
        "hourly_gl14": hourly_manifest.get("hourly_gl14_style"),
        "peak_check": peak,
        "time_basis_note": TIME_BASIS_NOTE,
        "campaign_manifest": campaign_manifest,
    }
    summary_path = figures_root / "figure_pack_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scorecard-dir",
        type=Path,
        default=Path("scorecards/b59_2020_load_schedule_dialin_24"),
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=Path("campaigns/runs/b59_2020_load_schedule_dialin_24/R22"),
    )
    parser.add_argument(
        "--measured-15min",
        type=Path,
        default=Path("scorecards/b59_2020_screening/source_targets/b59_2020_office_subtotal_15min.csv"),
    )
    parser.add_argument(
        "--measured-monthly",
        type=Path,
        default=Path("scorecards/b59_2020_screening/source_targets/b59_2020_monthly_records.csv"),
    )
    args = parser.parse_args()
    summary = publish_figures(
        scorecard_dir=args.scorecard_dir,
        run_dir=args.run_dir,
        measured_15min=args.measured_15min,
        measured_monthly=args.measured_monthly,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
