#!/usr/bin/env python3
"""Plot Building 59 measured HVAC evidence versus screening IDF settings.

Reads frozen hash-bound JSON only (no multi-GB telemetry download required).
Produces a comparison CSV plus PNG/SVG figures for the discrepancy audit.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

BG = "#0f1419"
PANEL = "#1a222c"
INK = "#e8eef4"
MUTED = "#9aa9b8"
GRID = "#2a3544"
MEASURED = "#3ecf8e"
SIMULATED = "#5eb1ff"
WARN = "#f0a04b"
FAIL = "#ff6b6b"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must be a JSON object")
    return payload


def _c_to_f(value_c: float) -> float:
    return value_c * 9.0 / 5.0 + 32.0


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
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = [output_dir / f"{stem}.png", output_dir / f"{stem}.svg"]
    fig.savefig(paths[0], dpi=150, bbox_inches="tight", facecolor=BG)
    fig.savefig(paths[1], bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    return paths


def _point_medians(role_block: dict[str, Any]) -> list[tuple[str, float]]:
    points = role_block.get("points") or {}
    rows: list[tuple[str, float]] = []
    for name, stats in points.items():
        if not isinstance(stats, dict):
            continue
        median = stats.get("median_sampled")
        if median is None:
            continue
        rows.append((name, float(median)))
    rows.sort(key=lambda item: item[0])
    return rows


def write_comparison_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "severity",
        "domain",
        "measured_or_runtime_evidence",
        "screening_idf_configuration",
        "difference_and_disposition",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def plot_severity_counts(rows: list[dict[str, Any]], output_dir: Path) -> list[Path]:
    counts = Counter(str(row.get("severity", "UNKNOWN")) for row in rows)
    order = [
        "BLOCKING_TOPOLOGY",
        "BLOCKING_CONTROL",
        "BLOCKING_UNIT_BINDING",
        "BLOCKING_SCOPE_TIME",
        "MAJOR",
        "PASS_ENGINE_ONLY",
    ]
    labels = [key for key in order if key in counts] + [
        key for key in sorted(counts) if key not in order
    ]
    values = [counts[key] for key in labels]
    colors = [
        FAIL
        if key.startswith("BLOCKING")
        else WARN
        if key == "MAJOR"
        else MEASURED
        for key in labels
    ]

    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    fig.patch.set_facecolor(BG)
    bars = ax.barh(labels[::-1], values[::-1], color=colors[::-1])
    _style(ax)
    ax.set_xlabel("Number of discrepancy domains")
    ax.set_title("B59 measured vs screening IDF — severity counts")
    for bar, value in zip(bars, values[::-1], strict=True):
        ax.text(
            bar.get_width() + 0.05,
            bar.get_y() + bar.get_height() / 2,
            str(value),
            va="center",
            color=INK,
            fontsize=9,
        )
    fig.text(
        0.01,
        0.01,
        "Source: config/b59_measured_vs_screening_idf.json · DISCREPANCY_AUDIT_NOT_CALIBRATED",
        color=MUTED,
        fontsize=8,
    )
    return _save(fig, output_dir, "fig01_severity_counts")


def plot_sat_setpoints(hvac: dict[str, Any], idf_sat_f: float, output_dir: Path) -> list[Path]:
    block = hvac["analysis"]["rtu_supply_air_temperature_setpoint"]
    medians = _point_medians(block)
    labels = [name.replace("_sat_sp_tn", "") for name, _ in medians]
    measured = [value for _, value in medians]

    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    fig.patch.set_facecolor(BG)
    x = range(len(labels))
    ax.bar(x, measured, color=MEASURED, label="BAS median SAT SP (°F)")
    ax.axhline(idf_sat_f, color=SIMULATED, linewidth=2.0, label=f"Screening IDF SAT ({idf_sat_f:.1f} °F)")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=0)
    ax.set_ylabel("Temperature (°F)")
    ax.set_title("RTU supply-air temperature setpoint: telemetry vs screening IDF")
    ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=INK)
    _style(ax)
    fig.text(
        0.01,
        0.01,
        "Source: config/b59_hvac_operating_evidence.json · sampled medians · source clock unresolved",
        color=MUTED,
        fontsize=8,
    )
    return _save(fig, output_dir, "fig02_rtu_sat_setpoint_vs_idf")


def plot_equipment_ratings(output_dir: Path) -> list[Path]:
    # Published rating vs screening champion parameters (documented in handoff).
    metrics = [
        ("Airflow\n(cfm / RTU)", 20_000.0, 13_500.0),
        ("Cooling capacity\n(kW / RTU)", 105.5, 142.4),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 4.5))
    fig.patch.set_facecolor(BG)
    for ax, (title, published, modeled) in zip(axes, metrics, strict=True):
        ax.bar([0, 1], [published, modeled], color=[MEASURED, SIMULATED])
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["Published /\nmeasured basis", "Screening\nIDF"])
        ax.set_title(title)
        delta_pct = 100.0 * (modeled - published) / published
        ax.text(
            0.5,
            max(published, modeled) * 1.02,
            f"Δ {delta_pct:+.1f}%",
            ha="center",
            color=WARN,
            fontsize=10,
        )
        _style(ax)
    fig.suptitle("RTU design ratings: published basis vs screening IDF", color=INK)
    fig.text(
        0.01,
        0.01,
        "Source: docs/B59_AGENT_HANDOFF.md + champion_parameters.json · not a calibrated claim",
        color=MUTED,
        fontsize=8,
    )
    fig.tight_layout(rect=(0, 0.06, 1, 0.92))
    return _save(fig, output_dir, "fig03_rtu_airflow_capacity_delta")


def plot_zone_setpoint_spread(
    hvac: dict[str, Any],
    *,
    idf_cool_f: float,
    idf_heat_f: float,
    output_dir: Path,
) -> list[Path]:
    cool = _point_medians(hvac["analysis"]["zone_cooling_temperature_setpoint"])
    heat = _point_medians(hvac["analysis"]["zone_heating_temperature_setpoint"])
    cool_vals = [value for _, value in cool]
    heat_vals = [value for _, value in heat]

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.8))
    fig.patch.set_facecolor(BG)
    for ax, values, idf_value, title in (
        (axes[0], cool_vals, idf_cool_f, "Zone cooling SP medians (°F)"),
        (axes[1], heat_vals, idf_heat_f, "Zone heating SP medians (°F)"),
    ):
        ax.hist(values, bins=12, color=MEASURED, edgecolor=GRID, alpha=0.9)
        ax.axvline(idf_value, color=SIMULATED, linewidth=2.0, label=f"IDF occupied {idf_value:.1f} °F")
        ax.set_xlabel("Point median (°F)")
        ax.set_ylabel("Zone count")
        ax.set_title(title)
        ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=INK, fontsize=8)
        _style(ax)
    fig.suptitle(
        f"Zone thermostat diversity ({len(cool_vals)} cool / {len(heat_vals)} heat points) vs one IDF setpoint",
        color=INK,
    )
    fig.text(
        0.01,
        0.01,
        "Source: config/b59_hvac_operating_evidence.json · one IDF setpoint erases measured diversity",
        color=MUTED,
        fontsize=8,
    )
    fig.tight_layout(rect=(0, 0.06, 1, 0.90))
    return _save(fig, output_dir, "fig04_zone_setpoint_diversity_vs_idf")


def plot_oa_fraction(hvac: dict[str, Any], idf_min_oa_ratio: float, output_dir: Path) -> list[Path]:
    # Prefer explicit OA evidence if present; otherwise skip gracefully.
    analysis = hvac.get("analysis") or {}
    key = None
    for candidate in (
        "rtu_outdoor_air_fraction",
        "outdoor_air_fraction",
        "oa_sa_ratio",
    ):
        if candidate in analysis:
            key = candidate
            break
    if key is None:
        # Fall back to documented comparison value for a single annotated bar.
        measured_median = 0.4846
        fig, ax = plt.subplots(figsize=(7.5, 4.2))
        fig.patch.set_facecolor(BG)
        ax.bar([0, 1], [measured_median, idf_min_oa_ratio], color=[MEASURED, SIMULATED])
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["Measured OA/SA\nmedian (plausible rows)", "IDF min OA /\ncoil airflow"])
        ax.set_ylabel("Fraction")
        ax.set_ylim(0, 1.0)
        ax.set_title("Outdoor-air fraction proxy vs screening IDF minimum")
        _style(ax)
        fig.text(
            0.01,
            0.01,
            "Source: b59_measured_vs_screening_idf.md · not a like-for-like minimum-OA test",
            color=MUTED,
            fontsize=8,
        )
        return _save(fig, output_dir, "fig05_oa_fraction_vs_idf")

    block = analysis[key]
    medians = _point_medians(block)
    labels = [name for name, _ in medians]
    values = [value for _, value in medians]
    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    fig.patch.set_facecolor(BG)
    ax.bar(range(len(labels)), values, color=MEASURED, label="Measured")
    ax.axhline(idf_min_oa_ratio, color=SIMULATED, linewidth=2.0, label=f"IDF min ratio {idf_min_oa_ratio:.3f}")
    ax.set_xticks(list(range(len(labels))))
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.set_ylabel("Fraction")
    ax.set_title("Outdoor-air fraction: telemetry vs IDF minimum ratio")
    ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=INK)
    _style(ax)
    return _save(fig, output_dir, "fig05_oa_fraction_vs_idf")


def build_pack(
    *,
    comparison_path: Path,
    hvac_path: Path,
    champion_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    comparison = _load(comparison_path)
    hvac = _load(hvac_path)
    champion = _load(champion_path)
    rows = list(comparison.get("comparison_rows") or [])
    if not rows:
        raise ValueError("comparison JSON has no comparison_rows")

    csv_path = output_dir / "measured_vs_idf_discrepancy_table.csv"
    write_comparison_csv(rows, csv_path)

    idf_sat_f = _c_to_f(14.4)  # documented fixed SAT in screening IDF
    idf_cool_f = _c_to_f(float(champion["occupied_cooling_setpoint_c"]))
    idf_heat_f = _c_to_f(float(champion["occupied_heating_setpoint_c"]))
    idf_min_oa = float(champion["minimum_outdoor_air_m3_s"]) / float(champion["coil_airflow_m3_s"])

    generated: list[Path] = [csv_path]
    generated.extend(plot_severity_counts(rows, output_dir))
    generated.extend(plot_sat_setpoints(hvac, idf_sat_f, output_dir))
    generated.extend(plot_equipment_ratings(output_dir))
    generated.extend(
        plot_zone_setpoint_spread(
            hvac,
            idf_cool_f=idf_cool_f,
            idf_heat_f=idf_heat_f,
            output_dir=output_dir,
        )
    )
    generated.extend(plot_oa_fraction(hvac, idf_min_oa, output_dir))

    severity = Counter(str(row.get("severity")) for row in rows)
    manifest = {
        "schema": "vibe23.b59_measured_vs_idf_figures.v1",
        "claim_status": comparison.get("claim_status"),
        "decision": comparison.get("decision"),
        "severity_counts": dict(severity),
        "sources": {
            "comparison": {"path": str(comparison_path.as_posix()), "sha256": _sha256(comparison_path)},
            "hvac_evidence": {"path": str(hvac_path.as_posix()), "sha256": _sha256(hvac_path)},
            "champion_parameters": {
                "path": str(champion_path.as_posix()),
                "sha256": _sha256(champion_path),
            },
        },
        "artifacts": [
            {
                "path": path.name,
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in generated
        ],
    }
    manifest_path = output_dir / "figure_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    generated.append(manifest_path)
    return manifest


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--comparison",
        type=Path,
        default=root / "config" / "b59_measured_vs_screening_idf.json",
    )
    parser.add_argument(
        "--hvac-evidence",
        type=Path,
        default=root / "config" / "b59_hvac_operating_evidence.json",
    )
    parser.add_argument(
        "--champion-parameters",
        type=Path,
        default=root / "scorecards" / "b59_2020_screening" / "champion_parameters.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=root
        / "scorecards"
        / "b59_2020_screening"
        / "figures"
        / "measured_vs_idf",
    )
    args = parser.parse_args()
    manifest = build_pack(
        comparison_path=args.comparison,
        hvac_path=args.hvac_evidence,
        champion_path=args.champion_parameters,
        output_dir=args.output_dir,
    )
    print(f"Wrote {len(manifest['artifacts'])} artifacts under {args.output_dir}")
    print(f"Severity counts: {manifest['severity_counts']}")
    print(f"Decision: {manifest['decision']}")


if __name__ == "__main__":
    main()
