"""A04 continuous-68°F monthly peak/kWh/cost vs actual utility bills (LIVE E+ CLI).

Reference arm only: 24/7 heating DualSP at 68°F baked into staged DSM_HTG_SP_*
schedules (not a compressor claim, not an operational DSM baseline). Uses the
EnergyPlus CLI so it can run beside a concurrent Gym/API RL campaign.

Sim costs: ILLUSTRATIVE FLAT_PLUS_DEMAND ($0.11/kWh + $12/kW).
Actual bill cost_usd comes from the utility CSV.
"""
from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP))

from eplus_gym.energyplus_cli import run_energyplus_cli
from eplus_gym.eplus_err import assert_eplus_quality, parse_eplus_err
from eplus_gym.epw_stage import stage_year_aware_epw
from eplus_gym.mega.tariff_modes import default_tariff_catalog
from eplus_gym.path_sanitize import redact_obj
from eplus_gym.site_env import require_site_root
from eplus_gym.stage_idf import stage_idf_for_period
from eplus_native.six_zone_htg_stage import ACTION_KEYS, dsm_htg_schedule_name

WATERMARK = (
    "CONTINUOUS 68°F REFERENCE — NOT OPERATIONAL BASELINE\n"
    "Sim costs: ILLUSTRATIVE FLAT_PLUS_DEMAND ($0.11/kWh + $12/kW) — NOT VERIFIED UTILITY PRICING"
)
HEATING_F = 68.0
HEATING_C = (HEATING_F - 32.0) * 5.0 / 9.0  # 20.0
INTERVAL_HOURS = 0.25
J_PER_KWH = 3.6e6
DEFAULT_MONTHS = [
    "2025-08",
    "2025-09",
    "2025-10",
    "2025-11",
    "2025-12",
    "2026-01",
    "2026-02",
    "2026-03",
    "2026-04",
    "2026-05",
]


def _month_bounds(ym: str) -> tuple[str, str]:
    y, m = ym.split("-")
    yi, mi = int(y), int(m)
    last = calendar.monthrange(yi, mi)[1]
    return f"{yi:04d}-{mi:02d}-01", f"{yi:04d}-{mi:02d}-{last:02d}"


def _load_utility(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    need = {"month", "kwh", "cost_usd"}
    missing = need - set(df.columns)
    if missing:
        raise SystemExit(f"utility CSV missing columns {sorted(missing)}: {path}")
    df = df.copy()
    df["month"] = df["month"].astype(str)
    if "billed_demand_kw" not in df.columns:
        if "demand_kw" not in df.columns:
            raise SystemExit("utility CSV needs billed_demand_kw or demand_kw")
        df["billed_demand_kw"] = df["demand_kw"]
    if "demand_kw" not in df.columns:
        df["demand_kw"] = df["billed_demand_kw"]
    return df


def _facility_kw_series(sim_dir: Path) -> pd.Series:
    """Electricity:Facility timestep → kW (J per interval / (h * 3.6e6))."""
    mtr = sim_dir / "eplusmtr.csv"
    src = mtr if mtr.is_file() else sim_dir / "eplusout.csv"
    if not src.is_file():
        raise FileNotFoundError(f"no eplusmtr/eplusout CSV in {sim_dir}")
    df = pd.read_csv(src)
    cols = list(df.columns)
    elec = None
    for c in cols:
        cl = c.lower()
        if "electricity:facility" in cl and "monthly" not in cl and "daily" not in cl:
            if "timestep" in cl or "time step" in cl:
                elec = c
                break
            if elec is None and "hourly" not in cl:
                elec = c
    if elec is None:
        raise ValueError(f"Electricity:Facility column missing in {src.name}")
    ts = cols[0]
    vals: list[float] = []
    for _, r in df.iterrows():
        stamp = str(r[ts]).strip()
        if not stamp or stamp.lower().startswith("date"):
            continue
        if pd.isna(r[elec]):
            continue
        j = float(r[elec])
        vals.append(j / (INTERVAL_HOURS * J_PER_KWH))
    if not vals:
        raise ValueError(f"no Electricity:Facility rows in {src.name}")
    return pd.Series(vals, dtype=float)


def _assert_staged_68(staged_idf: Path) -> str:
    text = staged_idf.read_text(encoding="utf-8")
    target = f"{HEATING_C:.4g}"
    for key in ACTION_KEYS:
        name = dsm_htg_schedule_name(key)
        if name not in text:
            raise ValueError(f"missing staged schedule {name}")
        # Schedule body must contain the constant 20 C value near the schedule name.
        idx = text.index(name)
        window = text[idx : idx + 400]
        if target not in window and "20;" not in window and "20.0" not in window:
            raise ValueError(f"{name} does not look like continuous {HEATING_F}°F ({HEATING_C}°C)")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_month(
    *,
    site: Path,
    epw: Path,
    idf: Path,
    out: Path,
    begin: str,
    end: str,
    timeout_s: float,
) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    staged_epw = stage_year_aware_epw(epw, out / f"staged_{epw.name}")["staged_epw"]
    staged = stage_idf_for_period(
        idf,
        out / f"staged_{idf.name}",
        begin,
        end,
        site_root=site,
        six_zone_actuators=True,
        six_zone_heating_f=HEATING_F,
    )
    schedule_sha = _assert_staged_68(staged)
    eplus_dir = out / "eplus"
    cli = run_energyplus_cli(
        idf=staged,
        epw=Path(staged_epw),
        output=eplus_dir,
        extra_args=["-r"],
        timeout_s=float(timeout_s),
    )
    if int(cli["returncode"]) != 0:
        raise RuntimeError(
            f"energyplus failed rc={cli['returncode']} stderr_tail={cli.get('stderr_tail')}"
        )
    err = eplus_dir / "eplusout.err"
    if not err.is_file():
        found = list(out.rglob("eplusout.err"))
        err = found[0] if found else err
    gate = parse_eplus_err(err)
    assert_eplus_quality(gate)
    fac = _facility_kw_series(eplus_dir)
    peak = float(fac.max())
    kwh = float(fac.sum() * INTERVAL_HOURS)
    fac.to_csv(out / "facility_kw_series.csv", index=False, header=["facility_kw"])
    return {
        "begin": begin,
        "end": end,
        "n_rows": int(len(fac)),
        "peak_kw": peak,
        "kwh": kwh,
        "heating_setpoint_f": HEATING_F,
        "heating_setpoint_c": HEATING_C,
        "continuous_conditioning": True,
        "engine": "energyplus_cli",
        "schedule_sha256": schedule_sha,
        "severe": int(gate.get("severe_count") or 0),
        "fatal": int(gate.get("fatal_count") or 0),
        "eplus_quality": gate,
        "cli_returncode": int(cli["returncode"]),
    }


def _illustrative_cost(kwh: float, demand_kw: float, *, energy: float, demand: float) -> float:
    return float(kwh) * float(energy) + float(demand_kw) * float(demand)


def _plot_compare(
    months: list[str],
    sim: list[float],
    actual: list[float],
    *,
    ylabel: str,
    title: str,
    out: Path,
    sim_label: str,
    actual_label: str,
) -> None:
    fig, ax = plt.subplots(figsize=(10, 4.5))
    x = list(range(len(months)))
    ax.plot(x, sim, marker="o", linewidth=2, label=sim_label, color="#0b6e4f")
    ax.plot(x, actual, marker="s", linewidth=2, label=actual_label, color="#1f4e79")
    ax.set_xticks(x)
    ax.set_xticklabels(months, rotation=45, ha="right")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    fig.text(0.5, 0.01, WATERMARK, ha="center", va="bottom", fontsize=8, color="#666666")
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(out, dpi=140)
    plt.close(fig)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--idf",
        type=Path,
        default=_APP / "models" / "eplus" / "lakeside_w2a_a04_dual_champion.idf",
    )
    p.add_argument("--site-root", type=Path, default=None)
    p.add_argument(
        "--utility-csv",
        type=Path,
        default=None,
        help="Default: $SITE_ROOT/utilities/electricity_utility_demand.csv",
    )
    p.add_argument("--months", nargs="+", default=DEFAULT_MONTHS)
    p.add_argument("--timeout-s", type=float, default=7200.0)
    p.add_argument(
        "--out-dir",
        type=Path,
        default=_APP / "docs" / "audits" / "figures" / "a04_continuous68_monthly_vs_utility",
    )
    p.add_argument(
        "--eplus-scratch",
        type=Path,
        default=None,
        help="Raw E+ outputs (not for GH). Default under $SITE_ROOT/reports/...",
    )
    args = p.parse_args()

    site = require_site_root(args.site_root)
    epw = site / "eplus" / "weather" / "madison_amy_202508_202608.epw"
    if not epw.is_file():
        raise SystemExit(f"EPW missing: {epw}")
    if not args.idf.is_file():
        raise SystemExit(f"IDF missing: {args.idf}")

    util_path = args.utility_csv or (site / "utilities" / "electricity_utility_demand.csv")
    util = _load_utility(util_path)
    util_by = {str(r.month): r for r in util.itertuples(index=False)}

    tariff = default_tariff_catalog()["FLAT_PLUS_DEMAND"]
    energy_rate = float(tariff.energy_rate_per_kwh)
    demand_rate = float(tariff.demand_rate_per_kw)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    scratch = Path(args.eplus_scratch) if args.eplus_scratch else (
        site / "reports" / "eplus_gym" / "a04_continuous68_monthly_vs_utility"
    )
    scratch.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for ym in args.months:
        if ym not in util_by:
            raise SystemExit(f"month {ym} not in utility CSV {util_path}")
        begin, end = _month_bounds(ym)
        month_scratch = scratch / ym.replace("-", "")
        print(f"[continuous68] CLI {ym} {begin}..{end} @ {HEATING_F}°F", flush=True)
        sim = run_month(
            site=site,
            epw=epw,
            idf=args.idf,
            out=month_scratch,
            begin=begin,
            end=end,
            timeout_s=args.timeout_s,
        )
        u = util_by[ym]
        util_kwh = float(u.kwh)
        util_peak = float(u.demand_kw)
        util_billed_demand = float(u.billed_demand_kw)
        util_cost = float(u.cost_usd)
        sim_cost_ill = _illustrative_cost(
            sim["kwh"], sim["peak_kw"], energy=energy_rate, demand=demand_rate
        )
        util_cost_ill = _illustrative_cost(
            util_kwh, util_billed_demand, energy=energy_rate, demand=demand_rate
        )
        row = {
            "month": ym,
            "begin": begin,
            "end": end,
            "sim_heating_setpoint_f": HEATING_F,
            "sim_peak_kw": sim["peak_kw"],
            "sim_kwh": sim["kwh"],
            "sim_cost_usd_illustrative_flat_plus_demand": sim_cost_ill,
            "utility_peak_kw": util_peak,
            "utility_billed_demand_kw": util_billed_demand,
            "utility_kwh": util_kwh,
            "utility_cost_usd_actual_bill": util_cost,
            "utility_cost_usd_repriced_illustrative_flat_plus_demand": util_cost_ill,
            "delta_kwh_sim_minus_utility": sim["kwh"] - util_kwh,
            "delta_peak_kw_sim_minus_utility_peak": sim["peak_kw"] - util_peak,
            "delta_cost_ill_sim_minus_actual_bill": sim_cost_ill - util_cost,
            "n_rows": sim["n_rows"],
            "severe": sim["severe"],
            "fatal": sim["fatal"],
            "schedule_sha256": sim["schedule_sha256"],
            "engine": sim["engine"],
        }
        rows.append(row)
        pd.DataFrame(rows).to_csv(out_dir / "monthly_continuous68_vs_utility.csv", index=False)
        (out_dir / "progress.json").write_text(
            json.dumps({"completed_months": [r["month"] for r in rows], "latest": row}, indent=2),
            encoding="utf-8",
        )
        print(
            f"[continuous68] {ym} sim_kwh={sim['kwh']:.0f} util_kwh={util_kwh:.0f} "
            f"sim_peak={sim['peak_kw']:.1f} util_peak={util_peak:.1f} "
            f"sim_ill_cost={sim_cost_ill:.0f} bill_cost={util_cost:.0f}",
            flush=True,
        )

    df = pd.DataFrame(rows)
    csv_path = out_dir / "monthly_continuous68_vs_utility.csv"
    df.to_csv(csv_path, index=False)

    months = df["month"].tolist()
    _plot_compare(
        months,
        df["sim_kwh"].tolist(),
        df["utility_kwh"].tolist(),
        ylabel="kWh",
        title="Monthly energy — A04 continuous 68°F vs utility billed kWh",
        out=out_dir / "monthly_kwh_continuous68_vs_utility.png",
        sim_label="E+ continuous 68°F",
        actual_label="Utility billed kWh",
    )
    _plot_compare(
        months,
        df["sim_peak_kw"].tolist(),
        df["utility_peak_kw"].tolist(),
        ylabel="kW",
        title="Monthly peak — A04 continuous 68°F (15-min max) vs utility demand_kw",
        out=out_dir / "monthly_peak_kw_continuous68_vs_utility.png",
        sim_label="E+ continuous 68°F peak",
        actual_label="Utility demand_kw",
    )
    _plot_compare(
        months,
        df["sim_cost_usd_illustrative_flat_plus_demand"].tolist(),
        df["utility_cost_usd_actual_bill"].tolist(),
        ylabel="USD",
        title="Monthly cost — illustrative sim ($0.11/kWh+$12/kW) vs actual bill",
        out=out_dir / "monthly_cost_continuous68_ill_vs_actual_bill.png",
        sim_label="Sim ILLUSTRATIVE FLAT_PLUS_DEMAND",
        actual_label="Utility cost_usd (actual bill)",
    )
    _plot_compare(
        months,
        df["sim_cost_usd_illustrative_flat_plus_demand"].tolist(),
        df["utility_cost_usd_repriced_illustrative_flat_plus_demand"].tolist(),
        ylabel="USD",
        title="Monthly cost — same ILLUSTRATIVE tariff on sim vs utility kWh+billed demand",
        out=out_dir / "monthly_cost_continuous68_vs_utility_repriced_ill.png",
        sim_label="Sim ILLUSTRATIVE",
        actual_label="Utility repriced ILLUSTRATIVE",
    )

    manifest = {
        "schema": "vibe22.a04_continuous68_monthly_vs_utility.v1",
        "idf": str(args.idf),
        "epw": str(epw),
        "utility_csv": str(util_path),
        "heating_setpoint_f": HEATING_F,
        "heating_setpoint_c": HEATING_C,
        "arm": "continuous_68",
        "engine": "energyplus_cli",
        "claim": "CONTINUOUS_68_REFERENCE_NOT_OPERATIONAL_BASELINE",
        "sim_cost_tariff": "FLAT_PLUS_DEMAND",
        "sim_cost_label": tariff.label,
        "energy_usd_per_kwh": energy_rate,
        "demand_usd_per_kw": demand_rate,
        "watermark": WATERMARK,
        "months": months,
        "artifacts": {
            "csv": str(csv_path.name),
            "png_kwh": "monthly_kwh_continuous68_vs_utility.png",
            "png_peak": "monthly_peak_kw_continuous68_vs_utility.png",
            "png_cost_vs_bill": "monthly_cost_continuous68_ill_vs_actual_bill.png",
            "png_cost_repriced": "monthly_cost_continuous68_vs_utility_repriced_ill.png",
        },
        "eplus_scratch_not_for_gh": str(scratch),
        "rows": rows,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(redact_obj(manifest), indent=2), encoding="utf-8"
    )
    print(f"[continuous68] wrote {csv_path}", flush=True)
    print(f"[continuous68] plots under {out_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
