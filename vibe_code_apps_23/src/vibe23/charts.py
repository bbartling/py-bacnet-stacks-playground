"""Publication-oriented measured-vs-simulated calibration chart packs.

The visual language follows the audit-first Vibe 22 reports: every figure is
derived from one immutable paired input, uses explicit units, and is accompanied
by a hash-bearing manifest.  Figures remain diagnostic until the provenance and
calibration gates are evaluated by the calibration scorecard.
"""
from __future__ import annotations

import json
import re
import warnings
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np
import pandas as pd

from vibe23.energyplus import sha256_file
from vibe23.metrics import score_calibration

DataKind = Literal["mean_power", "interval_energy"]

BG = "#0f1419"
PANEL = "#1a222c"
INK = "#e8eef4"
MUTED = "#9aa9b8"
GRID = "#2a3544"
MEASURED = "#3ecf8e"
SIMULATED = "#5eb1ff"
RESIDUAL = "#f0a04b"
FAIL = "#ff6b6b"


def _portable_path(path: Path) -> str:
    """Prefer a repository-relative manifest label when the source is local."""
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return str(resolved)


def _style(ax: plt.Axes) -> None:
    ax.set_facecolor(PANEL)
    ax.tick_params(colors=MUTED)
    ax.xaxis.label.set_color(MUTED)
    ax.yaxis.label.set_color(MUTED)
    ax.title.set_color(INK)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    ax.grid(True, color=GRID, alpha=0.55, linewidth=0.6)


def _save(fig: plt.Figure, output_dir: Path, stem: str) -> list[Path]:
    paths = [output_dir / f"{stem}.png", output_dir / f"{stem}.svg"]
    fig.savefig(paths[0], dpi=150, bbox_inches="tight", facecolor=BG)
    fig.savefig(paths[1], bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    return paths


def _load_paired_csv(
    path: Path,
    *,
    timestamp_column: str,
    measured_column: str,
    simulated_column: str,
    timezone: str | None,
) -> pd.DataFrame:
    frame = pd.read_csv(path)
    required = {timestamp_column, measured_column, simulated_column}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"comparison CSV is missing columns: {missing}")
    raw_timestamps = frame[timestamp_column]
    explicit_offset = raw_timestamps.astype(str).str.contains(r"(?:Z|[+-]\d{2}:?\d{2})$", regex=True)
    if timezone and explicit_offset.all():
        timestamps = pd.to_datetime(raw_timestamps, errors="raise", utc=True).dt.tz_convert(timezone)
    elif timezone and not explicit_offset.any():
        timestamps = pd.to_datetime(raw_timestamps, errors="raise").dt.tz_localize(
            timezone, ambiguous="raise", nonexistent="raise"
        )
    elif timezone:
        raise ValueError("timestamp column mixes offset-aware and naive values")
    else:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            timestamps = pd.to_datetime(raw_timestamps, errors="raise")
    if not isinstance(timestamps.dtype, pd.DatetimeTZDtype) and timestamps.dtype == object:
        if not timezone:
            raise ValueError(
                "timestamps contain mixed UTC offsets (often DST); supply the named --timezone explicitly"
            )
    values = pd.DataFrame(
        {
            "measured": pd.to_numeric(frame[measured_column], errors="raise").to_numpy(),
            "simulated": pd.to_numeric(frame[simulated_column], errors="raise").to_numpy(),
        },
        index=pd.DatetimeIndex(timestamps),
    ).sort_index()
    if values.index.has_duplicates:
        raise ValueError("comparison CSV contains duplicate timestamps")
    if len(values) < 2:
        raise ValueError("comparison CSV needs at least two paired rows")
    if not np.isfinite(values.to_numpy(dtype=float)).all():
        raise ValueError("comparison CSV contains null or non-finite values")
    return values.astype(float)


def _native_interval_hours(index: pd.DatetimeIndex) -> float:
    diffs = index.to_series().diff().dropna().dt.total_seconds().to_numpy() / 3600.0
    if not len(diffs) or np.any(diffs <= 0):
        raise ValueError("timestamps must be strictly increasing")
    return float(np.median(diffs))


def _integration_hours(
    index: pd.DatetimeIndex,
    *,
    interval_hours_override: float | None,
    max_gap_factor: float = 4.0,
) -> np.ndarray:
    """Return left-hold elapsed hours, failing closed across excessive gaps."""
    native = _native_interval_hours(index)
    if interval_hours_override is not None:
        override = float(interval_hours_override)
        if not np.isfinite(override) or override <= 0.0:
            raise ValueError("interval_hours must be finite and positive")
        return np.full(len(index), override, dtype=float)
    elapsed = index.to_series().diff().dropna().dt.total_seconds().to_numpy(dtype=float) / 3600.0
    if np.any(~np.isfinite(elapsed)) or np.any(elapsed <= 0.0):
        raise ValueError("timestamps must be strictly increasing")
    if float(np.max(elapsed)) > max_gap_factor * float(np.min(elapsed)):
        raise ValueError(
            "mean-power chart input contains an excessive timestamp gap; "
            "quality-control the paired series before integration"
        )
    return np.append(elapsed, native)


def _monthly_energy(
    paired: pd.DataFrame,
    *,
    data_kind: DataKind,
    interval_hours: np.ndarray,
) -> tuple[pd.DataFrame, pd.Series]:
    if data_kind == "mean_power":
        energy = paired.mul(interval_hours, axis=0)
    else:
        energy = paired.copy()
    monthly = energy.resample("MS").sum(min_count=1).dropna()
    counts = paired["measured"].resample("MS").count().reindex(monthly.index).fillna(0)
    return monthly, counts


def _complete_months(
    monthly: pd.DataFrame,
    counts: pd.Series,
    *,
    native_interval_hours: float,
) -> dict[str, Any]:
    direct_monthly = native_interval_hours >= 24.0 * 20.0
    rows = []
    for stamp in monthly.index:
        if direct_monthly:
            expected = 1
        else:
            month_end = stamp + pd.offsets.MonthBegin(1)
            expected = int(round((month_end - stamp).total_seconds() / 3600.0 / native_interval_hours))
        actual = int(counts.loc[stamp])
        fraction = actual / expected if expected else 0.0
        rows.append(
            {
                "month": stamp.strftime("%Y-%m"),
                "actual_pairs": actual,
                "expected_pairs": expected,
                "coverage_fraction": fraction,
                "complete": fraction >= 0.99,
            }
        )
    return {
        "definition": "at least 99% of expected paired intervals; direct monthly inputs expect one pair",
        "complete_month_count": sum(bool(row["complete"]) for row in rows),
        "months": rows,
    }


def _hourly_pairs(paired: pd.DataFrame, *, data_kind: DataKind) -> pd.DataFrame:
    aggregation = "mean" if data_kind == "mean_power" else "sum"
    if aggregation == "mean":
        return paired.resample("1h").mean().dropna()
    return paired.resample("1h").sum(min_count=1).dropna()


def _score_block(frame: pd.DataFrame, interval: Literal["monthly", "hourly"], *, parameters: int) -> dict[str, Any]:
    if len(frame) < 2 or parameters >= len(frame):
        return {
            "available": False,
            "n": len(frame),
            "p": parameters,
            "interval": interval,
            "reason": "at least two pairs and n > p are required",
            "threshold_passes": False,
            "calibration_claim_eligible": False,
        }
    score = score_calibration(frame["measured"], frame["simulated"], interval, p=parameters)
    payload = asdict(score)
    payload["threshold_passes"] = payload.pop("passes")
    return {
        "available": True,
        **payload,
        "calibration_claim_eligible": False,
    }


def _legend(ax: plt.Axes, **kwargs: Any) -> None:
    legend = ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=INK, **kwargs)
    if legend:
        for text in legend.get_texts():
            text.set_color(INK)


def _monthly_overlay(monthly: pd.DataFrame, *, energy_unit: str, title: str, out: Path) -> list[Path]:
    fig, ax = plt.subplots(figsize=(11.5, 5.5))
    fig.patch.set_facecolor(BG)
    _style(ax)
    x = np.arange(len(monthly))
    width = 0.38
    ax.bar(x - width / 2, monthly["measured"], width, color=MEASURED, label="Measured")
    ax.bar(x + width / 2, monthly["simulated"], width, color=SIMULATED, label="EnergyPlus")
    ax.set_xticks(x)
    ax.set_xticklabels([stamp.strftime("%Y-%m") for stamp in monthly.index], rotation=45, ha="right")
    ax.set_ylabel(f"Monthly energy ({energy_unit})")
    ax.set_title(f"{title}\nMonthly measured vs EnergyPlus · diagnostic, not a calibration claim")
    _legend(ax, loc="best")
    fig.tight_layout()
    return _save(fig, out, "fig01_monthly_measured_vs_energyplus")


def _gl14_scorecard(
    score: dict[str, Any],
    *,
    complete_month_count: int,
    title: str,
    out: Path,
) -> list[Path]:
    fig, ax = plt.subplots(figsize=(9.2, 4.8))
    fig.patch.set_facecolor(BG)
    _style(ax)
    if score.get("available"):
        values = [abs(float(score["nmbe_pct"])), float(score["cvrmse_pct"])]
        gates = [5.0, 15.0]
        labels = ["|NMBE|", "CV(RMSE)"]
        colors = [MEASURED if value <= gate else FAIL for value, gate in zip(values, gates)]
        y = np.arange(2)
        bars = ax.barh(y, values, color=colors, height=0.52)
        ax.scatter(gates, y, marker="|", s=460, linewidths=2.2, color=INK, label="Monthly gate")
        for bar, value, gate in zip(bars, values, gates):
            ax.text(
                max(value, gate) + 0.35,
                bar.get_y() + bar.get_height() / 2,
                f"{value:.2f}% · gate ≤ {gate:.0f}%",
                va="center",
                color=INK,
            )
        ax.set_yticks(y)
        ax.set_yticklabels(labels)
        ax.set_xlabel("Percent")
        upper = max(max(values), max(gates)) * 1.45
        ax.set_xlim(0, upper)
        if score.get("threshold_passes") and complete_month_count >= 12:
            gate_label = "NUMERIC GATE MET"
        elif score.get("threshold_passes"):
            gate_label = "THRESHOLDS MET · MONTH COUNT INCOMPLETE"
        else:
            gate_label = "NUMERIC GATE NOT MET"
        _legend(ax, loc="lower right")
    else:
        gate_label = "METRIC UNAVAILABLE"
        ax.text(
            0.5,
            0.55,
            score.get("reason", "insufficient complete monthly pairs"),
            ha="center",
            va="center",
            color=INK,
            transform=ax.transAxes,
        )
        ax.set_xticks([])
        ax.set_yticks([])
    count_label = f"{complete_month_count}/12 complete paired months"
    count_color = MEASURED if complete_month_count >= 12 else RESIDUAL
    fig.text(0.5, 0.03, count_label, ha="center", color=count_color, fontsize=11)
    ax.set_title(f"{title}\nMonthly Guideline 14-style scorecard · {gate_label}\nDiagnostic only")
    fig.tight_layout(rect=[0, 0.07, 1, 1])
    return _save(fig, out, "fig00_monthly_gl14_scorecard")


def _monthly_residual(monthly: pd.DataFrame, *, title: str, out: Path) -> list[Path]:
    measured = monthly["measured"].to_numpy(dtype=float)
    residual_pct = np.divide(
        100.0 * (monthly["simulated"].to_numpy(dtype=float) - measured),
        measured,
        out=np.full_like(measured, np.nan),
        where=measured != 0,
    )
    colors = [MEASURED if np.isfinite(value) and abs(value) <= 5.0 else FAIL for value in residual_pct]
    fig, ax = plt.subplots(figsize=(11.5, 5.2))
    fig.patch.set_facecolor(BG)
    _style(ax)
    x = np.arange(len(monthly))
    ax.bar(x, residual_pct, color=colors, width=0.72)
    ax.axhline(0.0, color=INK, linewidth=0.9)
    ax.axhspan(-5.0, 5.0, color=MEASURED, alpha=0.10, label="±5% visual reference")
    ax.set_xticks(x)
    ax.set_xticklabels([stamp.strftime("%Y-%m") for stamp in monthly.index], rotation=45, ha="right")
    ax.set_ylabel("Residual (%) · (EnergyPlus − measured) / measured")
    ax.set_title(f"{title}\nMonthly residual pattern")
    _legend(ax, loc="best")
    fig.tight_layout()
    return _save(fig, out, "fig02_monthly_residual_percent")


def _parity(paired: pd.DataFrame, *, unit: str, title: str, out: Path) -> list[Path]:
    fig, ax = plt.subplots(figsize=(7, 6.5))
    fig.patch.set_facecolor(BG)
    _style(ax)
    alpha = 0.65 if len(paired) < 2000 else 0.25
    size = 22 if len(paired) < 500 else 8
    ax.scatter(paired["measured"], paired["simulated"], s=size, alpha=alpha, color=SIMULATED)
    low = float(min(paired.min()))
    high = float(max(paired.max()))
    ax.plot([low, high], [low, high], color=MEASURED, linestyle="--", linewidth=1.4, label="1:1")
    ax.set_xlabel(f"Measured ({unit})")
    ax.set_ylabel(f"EnergyPlus ({unit})")
    ax.set_title(f"{title}\nPaired-interval parity")
    _legend(ax, loc="best")
    fig.tight_layout()
    return _save(fig, out, "fig03_paired_interval_parity")


def _load_duration(paired: pd.DataFrame, *, unit: str, title: str, out: Path) -> list[Path]:
    fig, ax = plt.subplots(figsize=(9, 4.8))
    fig.patch.set_facecolor(BG)
    _style(ax)
    measured = np.sort(paired["measured"].to_numpy(dtype=float))[::-1]
    simulated = np.sort(paired["simulated"].to_numpy(dtype=float))[::-1]
    exceedance = np.arange(len(measured)) / max(len(measured) - 1, 1) * 100.0
    ax.plot(exceedance, measured, color=MEASURED, linewidth=1.8, label="Measured")
    ax.plot(exceedance, simulated, color=SIMULATED, linewidth=1.8, label="EnergyPlus")
    ax.set_xlabel("Fraction of paired intervals exceeded (%)")
    ax.set_ylabel(unit)
    ax.set_title(f"{title}\nLoad-duration comparison")
    _legend(ax, loc="best")
    fig.tight_layout()
    return _save(fig, out, "fig04_load_duration")


def _typical_profiles(hourly: pd.DataFrame, *, unit: str, title: str, out: Path) -> list[Path]:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.7), sharey=True)
    fig.patch.set_facecolor(BG)
    is_weekday = hourly.index.dayofweek < 5
    for ax, mask, label in (
        (axes[0], is_weekday, "Weekday"),
        (axes[1], ~is_weekday, "Weekend"),
    ):
        _style(ax)
        subset = hourly.loc[mask]
        if subset.empty:
            ax.text(0.5, 0.5, "No paired data", ha="center", va="center", color=MUTED, transform=ax.transAxes)
        else:
            profile = subset.groupby(subset.index.hour).mean()
            ax.plot(profile.index, profile["measured"], color=MEASURED, marker="o", label="Measured")
            ax.plot(profile.index, profile["simulated"], color=SIMULATED, marker="o", label="EnergyPlus")
        ax.set_xlabel("Hour")
        ax.set_title(label)
        ax.set_xticks(range(0, 24, 3))
    axes[0].set_ylabel(unit)
    _legend(axes[0], loc="best")
    fig.suptitle(f"{title}\nMean hourly profiles", color=INK)
    fig.tight_layout()
    return _save(fig, out, "fig05_typical_day_profiles")


def _residual_heatmap(hourly: pd.DataFrame, *, unit: str, title: str, out: Path) -> list[Path]:
    residual = hourly["simulated"] - hourly["measured"]
    grid = residual.groupby([hourly.index.dayofweek, hourly.index.hour]).mean().unstack()
    grid = grid.reindex(index=range(7), columns=range(24))
    limit = float(np.nanpercentile(np.abs(grid.to_numpy(dtype=float)), 95))
    limit = max(limit, np.finfo(float).eps)
    fig, ax = plt.subplots(figsize=(11.5, 4.6))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(PANEL)
    image = ax.imshow(grid, aspect="auto", cmap="RdBu_r", vmin=-limit, vmax=limit)
    ax.set_yticks(range(7))
    ax.set_yticklabels(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], color=MUTED)
    ax.set_xticks(range(0, 24, 2))
    ax.set_xticklabels(range(0, 24, 2), color=MUTED)
    ax.set_xlabel("Hour", color=MUTED)
    ax.set_title(f"{title}\nMean residual heatmap · EnergyPlus − measured", color=INK)
    colorbar = fig.colorbar(image, ax=ax)
    colorbar.set_label(unit, color=MUTED)
    colorbar.ax.tick_params(colors=MUTED)
    fig.tight_layout()
    return _save(fig, out, "fig06_residual_weekday_hour_heatmap")


def build_calibration_chart_pack(
    comparison_csv: Path,
    output_dir: Path,
    *,
    timestamp_column: str = "timestamp",
    measured_column: str = "measured",
    simulated_column: str = "simulated",
    data_kind: DataKind = "mean_power",
    unit: str = "kW",
    energy_unit: str = "kWh",
    interval_hours: float | None = None,
    timezone: str | None = None,
    title: str = "LBNL Building 59 calibration",
    parameters: int = 1,
) -> dict[str, Any]:
    """Build PNG/SVG diagnostics plus a JSON and CSV evidence manifest."""
    comparison_csv = Path(comparison_csv).resolve()
    output_dir = Path(output_dir).resolve()
    if data_kind not in {"mean_power", "interval_energy"}:
        raise ValueError("data_kind must be mean_power or interval_energy")
    paired = _load_paired_csv(
        comparison_csv,
        timestamp_column=timestamp_column,
        measured_column=measured_column,
        simulated_column=simulated_column,
        timezone=timezone,
    )
    native_interval = _native_interval_hours(paired.index)
    integration_hours = _integration_hours(
        paired.index,
        interval_hours_override=interval_hours,
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    monthly, counts = _monthly_energy(
        paired,
        data_kind=data_kind,
        interval_hours=integration_hours,
    )
    completeness = _complete_months(monthly, counts, native_interval_hours=native_interval)
    complete_month_names = {row["month"] for row in completeness["months"] if row["complete"]}
    complete_monthly = monthly.loc[
        [stamp for stamp in monthly.index if stamp.strftime("%Y-%m") in complete_month_names]
    ]
    monthly_score = _score_block(complete_monthly, "monthly", parameters=parameters)
    hourly = _hourly_pairs(paired, data_kind=data_kind)
    hourly_score = (
        _score_block(hourly, "hourly", parameters=parameters)
        if native_interval <= 1.5
        else {
            "available": False,
            "n": 0,
            "p": parameters,
            "interval": "hourly",
            "reason": "native paired input is coarser than 1.5 hours",
            "threshold_passes": False,
            "calibration_claim_eligible": False,
        }
    )

    interval_unit = unit if data_kind == "mean_power" else energy_unit
    generated: list[Path] = []
    generated.extend(
        _gl14_scorecard(
            monthly_score,
            complete_month_count=completeness["complete_month_count"],
            title=title,
            out=output_dir,
        )
    )
    monthly_for_figures = complete_monthly if not complete_monthly.empty else monthly
    generated.extend(_monthly_overlay(monthly_for_figures, energy_unit=energy_unit, title=title, out=output_dir))
    generated.extend(_monthly_residual(monthly_for_figures, title=title, out=output_dir))
    generated.extend(_parity(paired, unit=interval_unit, title=title, out=output_dir))
    generated.extend(_load_duration(paired, unit=interval_unit, title=title, out=output_dir))
    if native_interval <= 1.5:
        generated.extend(_typical_profiles(hourly, unit=interval_unit, title=title, out=output_dir))
        generated.extend(_residual_heatmap(hourly, unit=interval_unit, title=title, out=output_dir))

    monthly_csv = output_dir / "monthly_comparison.csv"
    monthly_out = monthly.copy()
    monthly_out.index = monthly_out.index.strftime("%Y-%m")
    monthly_out["residual"] = monthly_out["simulated"] - monthly_out["measured"]
    monthly_out["residual_pct"] = np.where(
        monthly_out["measured"] != 0,
        100.0 * monthly_out["residual"] / monthly_out["measured"],
        np.nan,
    )
    coverage_by_month = {row["month"]: row for row in completeness["months"]}
    monthly_out["coverage_fraction"] = [coverage_by_month[name]["coverage_fraction"] for name in monthly_out.index]
    monthly_out["complete"] = [coverage_by_month[name]["complete"] for name in monthly_out.index]
    monthly_out.to_csv(monthly_csv, index_label="month")
    generated.append(monthly_csv)

    manifest = {
        "schema": "vibe23.calibration_chart_pack.v1",
        "claim_status": "DIAGNOSTIC_ONLY_NOT_A_CALIBRATION_CLAIM",
        "title": title,
        "source": {
            "path": _portable_path(comparison_csv),
            "sha256": sha256_file(comparison_csv),
            "timestamp_column": timestamp_column,
            "measured_column": measured_column,
            "simulated_column": simulated_column,
            "paired_rows": len(paired),
            "start": paired.index.min().isoformat(),
            "end": paired.index.max().isoformat(),
        },
        "semantics": {
            "data_kind": data_kind,
            "interval_unit": interval_unit,
            "energy_unit": energy_unit,
            "native_interval_hours_median": native_interval,
            "energy_integration": (
                "constant_interval_override"
                if interval_hours is not None
                else "elapsed_time_left_hold; final_sample_uses_median_native_interval"
            ),
            "energy_interval_hours_min": float(np.min(integration_hours)),
            "energy_interval_hours_max": float(np.max(integration_hours)),
            "timezone": str(paired.index.tz) if paired.index.tz is not None else None,
            "residual_sign": "simulated_minus_measured",
        },
        "monthly_gl14_style": {
            **monthly_score,
            "minimum_complete_months": 12,
            "minimum_complete_month_count_passes": completeness["complete_month_count"] >= 12,
        },
        "hourly_gl14_style": hourly_score,
        "monthly_completeness": completeness,
        "artifacts": [],
        "claim_boundary": (
            "Charts and standalone metrics are diagnostic. A Building 59 calibration claim additionally requires "
            "complete provenance, a runnable hashed model/AMY, at least 12 complete paired months for the monthly "
            "gate, repeatability, and the applicable peak/end-use/zone/control/transient gates."
        ),
    }
    for path in generated:
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
    manifest_path = output_dir / "chart_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def build_gl14_campaign_progress(
    campaign_log_csv: Path,
    output_dir: Path,
    *,
    title: str = "LBNL Building 59 monthly calibration campaign",
) -> dict[str, Any]:
    """Plot iteration progress from an immutable, hash-bearing campaign ledger."""
    campaign_log_csv = Path(campaign_log_csv).resolve()
    output_dir = Path(output_dir).resolve()
    frame = pd.read_csv(campaign_log_csv)
    required = {
        "iteration",
        "parameter_family",
        "nmbe_pct",
        "cvrmse_pct",
        "complete_months",
        "idf_sha256",
        "epw_sha256",
        "target_sha256",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"campaign log is missing columns: {missing}")
    if frame.empty:
        raise ValueError("campaign log is empty")
    numeric_columns = ("iteration", "nmbe_pct", "cvrmse_pct", "complete_months")
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    if not np.isfinite(frame[list(numeric_columns)].to_numpy(dtype=float)).all():
        raise ValueError("campaign log contains non-finite metrics")
    if frame["iteration"].duplicated().any():
        raise ValueError("campaign log contains duplicate iteration numbers")
    hash_re = re.compile(r"^[0-9a-f]{64}$")
    for column in ("idf_sha256", "epw_sha256", "target_sha256"):
        bad = [value for value in frame[column].astype(str) if not hash_re.fullmatch(value)]
        if bad:
            raise ValueError(f"campaign log {column} must contain lowercase SHA-256 values")
    frame = frame.sort_values("iteration").reset_index(drop=True)
    frame["numeric_gate_met"] = (
        (frame["nmbe_pct"].abs() <= 5.0)
        & (frame["cvrmse_pct"] <= 15.0)
        & (frame["complete_months"] >= 12)
    )
    frame["gate_distance"] = np.maximum(frame["nmbe_pct"].abs() / 5.0, frame["cvrmse_pct"] / 15.0)
    best = frame.loc[frame["gate_distance"].idxmin()]
    first_gate = frame.loc[frame["numeric_gate_met"]].head(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(11.5, 5.6))
    fig.patch.set_facecolor(BG)
    _style(ax)
    iterations = frame["iteration"].astype(int)
    ax.plot(iterations, frame["nmbe_pct"].abs(), color=SIMULATED, marker="o", linewidth=2, label="|NMBE| %")
    ax.plot(iterations, frame["cvrmse_pct"], color=RESIDUAL, marker="s", linewidth=2, label="CV(RMSE) %")
    ax.axhline(5.0, color=SIMULATED, linestyle="--", linewidth=1.2, alpha=0.8, label="NMBE gate 5%")
    ax.axhline(15.0, color=RESIDUAL, linestyle="--", linewidth=1.2, alpha=0.8, label="CV(RMSE) gate 15%")
    if not first_gate.empty:
        first = first_gate.iloc[0]
        ax.axvline(int(first["iteration"]), color=MEASURED, linestyle=":", linewidth=1.8)
        ax.annotate(
            f"first provisional numeric gate\niter {int(first['iteration'])}",
            xy=(int(first["iteration"]), max(abs(float(first["nmbe_pct"])), float(first["cvrmse_pct"]))),
            xytext=(8, 18),
            textcoords="offset points",
            color=INK,
            arrowprops={"arrowstyle": "->", "color": MEASURED},
        )
    ax.set_xlabel("Published iteration")
    ax.set_ylabel("Percent")
    ax.set_xticks(iterations)
    ax.set_title(f"{title}\nGuideline 14-style progress · diagnostic until full campaign gates pass")
    _legend(ax, ncol=2, loc="best")
    fig.tight_layout()
    written = _save(fig, output_dir, "monthly_gl14_progress_by_iteration")

    manifest = {
        "schema": "vibe23.gl14_campaign_progress.v1",
        "claim_status": (
            "NUMERIC_MONTHLY_GATE_MET_PROVISIONAL"
            if bool(frame["numeric_gate_met"].any())
            else "CALIBRATION_IN_PROGRESS_NUMERIC_GATE_NOT_MET"
        ),
        "source": {"path": _portable_path(campaign_log_csv), "sha256": sha256_file(campaign_log_csv)},
        "iteration_count": len(frame),
        "best_iteration_by_gate_distance": int(best["iteration"]),
        "first_numeric_gate_iteration": None if first_gate.empty else int(first_gate.iloc[0]["iteration"]),
        "parameter_family_order": frame["parameter_family"].astype(str).tolist(),
        "artifacts": [
            {
                "path": path.name,
                "sha256": sha256_file(path),
                "media_type": "image/png" if path.suffix == ".png" else "image/svg+xml",
            }
            for path in written
        ],
        "claim_boundary": (
            "This plot verifies only the numeric monthly thresholds and complete-month count recorded in the log. "
            "MONTHLY_CALIBRATED additionally requires verified measured/simulated provenance, successful repeatable "
            "EnergyPlus runs, scope/weather alignment, and review for compensating physical errors."
        ),
    }
    (output_dir / "campaign_chart_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


__all__ = ["build_calibration_chart_pack", "build_gl14_campaign_progress"]
