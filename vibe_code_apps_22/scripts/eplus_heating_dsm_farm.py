#!/usr/bin/env python
"""Native EnergyPlus heating DSM farm (fail-closed).

Every accepted training label comes from a validated native E+ run of the
staged DSM-eligible utility champion. No BAS physics_proxy / bootstrap path.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

_APP = Path(__file__).resolve().parents[1]
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))
_ML = _APP / "ml"
if str(_ML) not in sys.path:
    sys.path.insert(0, str(_ML))

from lakeside.paths import site_root  # noqa: E402
from eplus_native.extract import (  # noqa: E402
    filter_stamps_for_day,
    load_timestep_proxy_kw,
    to_hourly_mean_kw,
)
from eplus_native.hashes import sha256_file  # noqa: E402
from eplus_native.idf_stage import patch_run_period  # noqa: E402
from eplus_native.runner import run_energyplus  # noqa: E402
from feature_compile_heating_dsm import STRATEGY_IDS  # noqa: E402

ZONE_LABELS = ["1F-A", "1F-B", "1F-C", "1F-D", "2F-A", "2F-B"]


def _eligible_idf(root: Path) -> Path:
    ptr = root / "eplus" / "models" / "staged" / "DSM_ELIGIBLE.json"
    if not ptr.is_file():
        raise FileNotFoundError(
            f"missing {ptr} — run scripts/eplus_stage_repair_and_rescore.py first"
        )
    j = json.loads(ptr.read_text(encoding="utf-8"))
    p = Path(j["staged_idf"])
    if not p.is_file():
        raise FileNotFoundError(p)
    return p


def _input_hash(idf_text: str, scenario: dict) -> str:
    h = hashlib.sha256()
    h.update(idf_text.encode("utf-8"))
    safe = {
        k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in scenario.items()
    }
    h.update(json.dumps(safe, sort_keys=True).encode("utf-8"))
    return h.hexdigest()[:16]


def _patch_htg_schedule_for_strategy(text: str, strategy_id: str, seed: int) -> str:
    """Documented control patch: only SCH_HtgSP (and optional availability)."""
    rng = np.random.default_rng(seed)
    if strategy_id == "flat_24_7":
        # constant occupied heating SP
        body = """SCHEDULE:COMPACT,
    SCH_HtgSP,                !- Name
    Temperature,              !- Schedule Type Limits Name
    Through: 12/31,           !- Field 1
    For: AllDays,             !- Field 2
    Until: 24:00,             !- Field 3
    20.00;                    !- Field 4
"""
    elif strategy_id == "deep_setback":
        body = """SCHEDULE:COMPACT,
    SCH_HtgSP,                !- Name
    Temperature,              !- Schedule Type Limits Name
    Through: 12/31,           !- Field 1
    For: AllDays,             !- Field 2
    Until: 07:00,             !- Field 3
    15.56,                    !- Field 4
    Until: 16:00,             !- Field 5
    20.00,                    !- Field 6
    Until: 24:00,             !- Field 7
    15.56;                    !- Field 8
"""
    elif strategy_id == "stagger_preheat":
        body = """SCHEDULE:COMPACT,
    SCH_HtgSP,                !- Name
    Temperature,              !- Schedule Type Limits Name
    Through: 12/31,           !- Field 1
    For: AllDays,             !- Field 2
    Until: 05:00,             !- Field 3
    17.78,                    !- Field 4
    Until: 08:00,             !- Field 5
    20.00,                    !- Field 6
    Until: 16:00,             !- Field 7
    20.00,                    !- Field 8
    Until: 24:00,             !- Field 9
    17.78;                    !- Field 10
"""
    elif strategy_id == "morning_all_on":
        body = """SCHEDULE:COMPACT,
    SCH_HtgSP,                !- Name
    Temperature,              !- Schedule Type Limits Name
    Through: 12/31,           !- Field 1
    For: AllDays,             !- Field 2
    Until: 05:00,             !- Field 3
    16.67,                    !- Field 4
    Until: 16:00,             !- Field 5
    20.00,                    !- Field 6
    Until: 24:00,             !- Field 7
    16.67;                    !- Field 8
"""
    elif strategy_id.startswith("prbs_"):
        # PRBS-like: random daytime SP between setback and occupied, dwell ≥2h blocks
        night = 17.78
        day_vals = [18.33, 19.0, 20.0, 20.0]
        blocks = []
        h = 0
        while h < 24:
            dwell = int(rng.integers(2, 5))
            until = min(24, h + dwell)
            sp = night if h < 5 or h >= 16 else float(rng.choice(day_vals))
            blocks.append((until, sp))
            h = until
        lines = [
            "SCHEDULE:COMPACT,",
            "    SCH_HtgSP,                !- Name",
            "    Temperature,              !- Schedule Type Limits Name",
            "    Through: 12/31,           !- Field 1",
            "    For: AllDays,             !- Field 2",
        ]
        fi = 3
        for until, sp in blocks:
            lines.append(f"    Until: {until:02d}:00,             !- Field {fi}")
            fi += 1
            end = ";" if until == 24 else ","
            lines.append(f"    {sp:.2f}{end}                    !- Field {fi}")
            fi += 1
        body = "\n".join(lines) + "\n"
    else:
        # baseline — leave schedule as staged
        return text

    import re

    pat = re.compile(r"SCHEDULE:COMPACT,\s*\n\s*SCH_HtgSP\s*,.*?;", re.I | re.S)
    if not pat.search(text):
        raise ValueError("SCH_HtgSP not found for strategy patch")
    return pat.sub(body.rstrip(), text, count=1)


def _cold_shoulder_days(n_cold: int = 12, n_shoulder: int = 6) -> list[date]:
    """Deterministic day list inside AMY window (2025-08-01 .. 2026-07-02)."""
    # Cold: Jan–Feb 2026; shoulder: Oct–Nov 2025
    cold = [date(2026, 1, 5 + i * 2) for i in range(n_cold)]
    shoulder = [date(2025, 10, 6 + i * 3) for i in range(n_shoulder)]
    return cold + shoulder


def build_scenarios(*, smoke: bool, medium: bool) -> list[dict]:
    days = _cold_shoulder_days(4, 2) if smoke else _cold_shoulder_days(12, 6)
    scenarios = []
    # Always include paired baseline + named strategies
    strategies = list(STRATEGY_IDS)
    if smoke:
        strategies = ["baseline", "stagger_preheat", "flat_24_7", "prbs_z1"]
        days = days[:3]
    elif medium:
        strategies = list(STRATEGY_IDS) + [f"prbs_{i}" for i in range(4)]
    for d in days:
        for sid in strategies:
            scenarios.append(
                {
                    "scenario_id": f"{d.isoformat()}_{sid}",
                    "day": d.isoformat(),
                    "strategy_id": sid,
                    "begin": d,
                    "end": d,
                    "seed": int(d.toordinal() * 17 + hash(sid) % 997),
                }
            )
    return scenarios


def _rows_from_run(
    hourly: pd.DataFrame,
    *,
    scenario: dict,
    run_id: str,
    idf_sha: str,
    epw_sha: str,
) -> list[dict]:
    rows = []
    d = scenario["day"]
    sid = scenario["strategy_id"]
    for i, r in hourly.iterrows():
        he = int(i % 24) if False else None
        # Prefer parse hour from stamp
        stamp = str(r.get("eplus_stamp", ""))
        hour_ending = 0
        import re

        m = re.search(r"(\d{1,2}):(\d{2}):(\d{2})$", stamp)
        if m:
            hour_ending = int(m.group(1)) % 24
        dt = date.fromisoformat(d)
        rows.append(
            {
                "day": d,
                "hour_ending": hour_ending,
                "month": dt.month,
                "doy": int(dt.timetuple().tm_yday),
                "is_weekend": 1.0 if dt.weekday() >= 5 else 0.0,
                "facility_kw": float(r["site_electric_proxy_kw"]),
                "strategy_id": sid if sid.startswith("prbs") else sid,
                "simulation_id": run_id,
                "run_id": run_id,
                "scenario_id": scenario["scenario_id"],
                "provenance": "ENERGYPLUS_NATIVE_RUN",
                "idf_sha256": idf_sha,
                "epw_sha256": epw_sha,
                "heat_cop_proxy": 3.5,
                "cool_cop_proxy": 4.5,
                "schema_version": "lakeside.heating_dsm_farm.native.v1",
                "oat_f": np.nan,  # filled later from weather if available
                "rh_pct": 50.0,
                "ghi": 0.0,
                "occupied": 1.0 if 7 <= hour_ending < 16 else 0.0,
                "facility_kw_bas": float(r["site_electric_proxy_kw"]),
            }
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--smoke", action="store_true", help="~8–12 short native runs")
    ap.add_argument("--medium", action="store_true", help="~80–120 scenario-days")
    ap.add_argument(
        "--out",
        type=Path,
        default=_APP / "ml" / "artifacts" / "heating_dsm_eplus_farm_hourly.parquet",
    )
    args = ap.parse_args(argv)
    if not args.smoke and not args.medium:
        args.smoke = True

    os.environ.setdefault(
        "LAKESIDE_SITE_ROOT",
        r"C:\Users\ben\OneDrive\Desktop\testing\sp_creekside",
    )
    root = site_root()
    idf_src = _eligible_idf(root)
    epw = root / "eplus" / "weather" / "madison_amy_202508_202607.epw"
    farm_root = root / "eplus" / "dsm_farm"
    farm_root.mkdir(parents=True, exist_ok=True)
    index_path = farm_root / "farm_index.jsonl"

    base_text = idf_src.read_text(encoding="utf-8")
    idf_sha = sha256_file(idf_src)
    epw_sha = sha256_file(epw)
    scenarios = build_scenarios(smoke=args.smoke, medium=args.medium)
    print(f"farm scenarios={len(scenarios)} idf={idf_src.name}", flush=True)

    all_rows: list[dict] = []
    accepted = 0
    rejected = 0
    for sc in scenarios:
        run_id = sc["scenario_id"].replace(":", "")
        scen_hash = _input_hash(base_text, sc)
        run_dir = farm_root / f"{run_id}_{scen_hash}"
        man_path = run_dir / "run_manifest.json"
        if man_path.is_file():
            man = json.loads(man_path.read_text(encoding="utf-8"))
            if man.get("accepted"):
                # resume cache hit
                hourly_path = run_dir / "hourly_proxy.parquet"
                if hourly_path.is_file():
                    hourly = pd.read_parquet(hourly_path)
                    all_rows.extend(
                        _rows_from_run(
                            hourly, scenario=sc, run_id=run_id, idf_sha=idf_sha, epw_sha=epw_sha
                        )
                    )
                    accepted += 1
                    continue

        text = _patch_htg_schedule_for_strategy(base_text, sc["strategy_id"], sc["seed"])
        d0: date = sc["begin"]
        text = patch_run_period(
            text,
            begin_month=d0.month,
            begin_day=d0.day,
            end_month=d0.month,
            end_day=d0.day,
            begin_year=d0.year,
            end_year=d0.year,
            name=f"DSM_{d0.isoformat()}",
        )
        if run_dir.exists():
            shutil.rmtree(run_dir, ignore_errors=True)
        run_dir.mkdir(parents=True)
        idf_path = run_dir / "model.idf"
        idf_path.write_text(text, encoding="utf-8")

        man = run_energyplus(
            run_id=run_id,
            scenario_id=sc["scenario_id"],
            idf_path=idf_path,
            epw_path=epw,
            output_dir=run_dir / "sim",
            require_zero_severe=True,
            allow_staged_idf=True,
        )
        with index_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(man.to_dict()) + "\n")
        if not man.accepted:
            rejected += 1
            print(f"REJECT {run_id}: {man.reject_reasons}", flush=True)
            continue
        try:
            ts = load_timestep_proxy_kw(run_dir / "sim", interval_hours=0.25)
            ts = filter_stamps_for_day(ts, sc["day"])
            hourly = to_hourly_mean_kw(ts)
            hourly.to_parquet(run_dir / "hourly_proxy.parquet", index=False)
        except Exception as e:
            rejected += 1
            print(f"EXTRACT FAIL {run_id}: {e}", flush=True)
            continue
        accepted += 1
        all_rows.extend(
            _rows_from_run(hourly, scenario=sc, run_id=run_id, idf_sha=idf_sha, epw_sha=epw_sha)
        )
        print(f"OK {run_id} hours={len(hourly)}", flush=True)

    if accepted == 0:
        print("NO ACCEPTED RUNS — farm failed closed", file=sys.stderr)
        return 1

    farm = pd.DataFrame(all_rows)
    # Attach weather OAT when available
    try:
        from artifact_paths import weather_history_csv, demand_hourly_csv
        from build_bootstrap_dataset import _load_weather_hourly, _load_hourly_demand

        wx = _load_weather_hourly(weather_history_csv())
        if len(wx):
            farm = farm.merge(wx, on=["day", "hour_ending"], how="left", suffixes=("", "_wx"))
            if "oat_f_wx" in farm.columns:
                farm["oat_f"] = farm["oat_f"].fillna(farm["oat_f_wx"])
        dem = _load_hourly_demand(demand_hourly_csv())
        if len(dem) and "oat_f" in dem.columns:
            # fill remaining oat from demand file
            m = dem[["day", "hour_ending", "oat_f"]].rename(columns={"oat_f": "oat_dem"})
            farm = farm.merge(m, on=["day", "hour_ending"], how="left")
            farm["oat_f"] = farm["oat_f"].fillna(farm["oat_dem"])
    except Exception as e:
        print(f"weather attach skipped: {e}", flush=True)

    farm["oat_f"] = farm["oat_f"].fillna(25.0)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    farm.to_parquet(args.out, index=False)
    summary = {
        "n_rows": int(len(farm)),
        "n_scenarios_accepted": accepted,
        "n_scenarios_rejected": rejected,
        "n_days": int(farm["day"].nunique()),
        "strategies": sorted(farm["strategy_id"].astype(str).unique().tolist()),
        "provenance": "ENERGYPLUS_NATIVE_RUN",
        "idf_sha256": idf_sha,
        "epw_sha256": epw_sha,
        "staged_idf": str(idf_src),
        "out": str(args.out),
        "honesty": (
            "Native EnergyPlus IdealLoads + fixed-COP electrical proxy. "
            "Not a detailed GSHP/GLHE plant. Fail-closed: rejected runs excluded."
        ),
    }
    (args.out.parent / "eplus_farm_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
