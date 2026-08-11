#!/usr/bin/env python
"""Native EnergyPlus paired heating DSM farm (fail-closed, hybrid Phase 3).

Produces 15-min rows with facility IdealLoads+COP kW + 6-area MAT (°F), paired
baseline/DSM arms, per-area thermostat + IdealLoads availability controls,
stable hashlib seeds, and hash-gated immutable manifests.

Provenance: ENERGYPLUS_NATIVE_RUN · honesty: HYBRID_SCREENING
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
from typing import Any

import numpy as np
import pandas as pd

_APP = Path(__file__).resolve().parents[1]
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))
_ML = _APP / "archive" / "ml"
if str(_ML) not in sys.path:
    sys.path.insert(0, str(_ML))

from lakeside.paths import site_root  # noqa: E402
from eplus_native.extract import (  # noqa: E402
    ZONE_TEMP_COLS,
    attach_utc_timestamps,
    filter_stamps_for_day,
    load_timestep_proxy_and_mat,
)
from eplus_native.hashes import sha256_file  # noqa: E402
from eplus_native.idf_stage import (  # noqa: E402
    DSM_ZONES,
    ensure_per_area_dsm_schedules,
    patch_run_period,
)
from eplus_native.runner import run_energyplus  # noqa: E402
from feature_compile_heating_dsm import (  # noqa: E402
    HP_ON_COLS,
    STRATEGY_IDS,
    ZONE_TEMP_COLS as ML_ZONE_TEMP_COLS,
)

SCHEMA_VERSION = "lakeside.heating_dsm_farm.paired_15min.v1"
OUT_STEM = "heating_dsm_eplus_paired_15min_v1"
PROVENANCE = "ENERGYPLUS_NATIVE_RUN"
HONESTY = "HYBRID_SCREENING"
# IdealLoads+COP is structural / screening only — not a W2A plant twin.
PHYSICS_FAMILY = "STRUCTURAL_LOAD_DIAGNOSTIC"
PHYSICS_DETAIL = "IdealLoads + fixed-COP (gshp filename naming only; not W2A_PHYSICAL_DSM)"

# °C setpoints written into IDF schedules
OCC_HTG_C = 20.0  # 68°F
UNOCC_HTG_C = 18.33  # ~65°F
DEEP_SETBACK_C = 15.56  # 60°F
FLAT_HTG_C = 20.0

ZONE_SHORT = {
    "1F_Area_A": "1F_A",
    "1F_Area_B": "1F_B",
    "1F_Area_C": "1F_C",
    "1F_Area_D": "1F_D",
    "2F_Area_A": "2F_A",
    "2F_Area_B": "2F_B",
}
assert list(ZONE_TEMP_COLS.values()) == list(ML_ZONE_TEMP_COLS)


def _jsonable(obj: Any) -> Any:
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    return obj


def stable_seed_from_scenario(scenario: dict) -> int:
    """Deterministic seed from scenario dict via hashlib — never Python hash()."""
    payload = {k: v for k, v in scenario.items() if k != "seed"}
    digest = hashlib.sha256(
        json.dumps(_jsonable(payload), sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return int(digest[:8], 16)


def input_hash(idf_text: str, scenario: dict) -> str:
    h = hashlib.sha256()
    h.update(idf_text.encode("utf-8"))
    h.update(
        json.dumps(_jsonable(scenario), sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    return h.hexdigest()


def control_regime_for(strategy_id: str) -> str:
    if strategy_id == "baseline":
        return "baseline"
    if strategy_id.startswith("prbs"):
        return "prbs"
    if strategy_id in STRATEGY_IDS:
        return strategy_id
    return strategy_id


def _blocks_from_hourly(values_c: list[float]) -> list[tuple[int, int, float]]:
    """24 hourly values → Schedule:Compact Until blocks (merge consecutive equals)."""
    assert len(values_c) == 24
    blocks: list[tuple[int, int, float]] = []
    i = 0
    while i < 24:
        v = float(values_c[i])
        j = i + 1
        while j < 24 and float(values_c[j]) == v:
            j += 1
        until_h = j  # end at j:00; when j==24 → 24:00
        blocks.append((until_h if until_h < 24 else 24, 0, v))
        i = j
    return blocks


def _avail_from_hp(hp_hourly: list[float]) -> list[tuple[int, int, float]]:
    return _blocks_from_hourly([1.0 if x >= 0.5 else 0.0 for x in hp_hourly])


def _baseline_htg_hourly() -> list[float]:
    # K-12-ish: unocc overnight, occ 07–16
    return [OCC_HTG_C if 7 <= h < 16 else UNOCC_HTG_C for h in range(24)]


def _baseline_hp_hourly() -> list[float]:
    # IdealLoads available ~05:30–15:30 weekday-like (AllDays for farm single-day)
    return [1.0 if 6 <= h < 16 else 0.0 for h in range(24)]


def build_area_controls(strategy_id: str, seed: int) -> dict[str, Any]:
    """Per-area heating SP (°C hourly) + hp_on (0/1 hourly) + regime metadata."""
    rng = np.random.default_rng(seed)
    zones = list(DSM_ZONES)
    htg: dict[str, list[float]] = {}
    hp: dict[str, list[float]] = {}
    meta: dict[str, Any] = {
        "strategy_id": strategy_id,
        "control_regime": control_regime_for(strategy_id),
        "preheat_lead_h": 0.0,
        "stagger_min": 0.0,
        "unocc_htg_sp_f": UNOCC_HTG_C * 9 / 5 + 32,
        "occ_htg_sp_f": OCC_HTG_C * 9 / 5 + 32,
    }

    if strategy_id == "baseline":
        base_h = _baseline_htg_hourly()
        base_a = _baseline_hp_hourly()
        for z in zones:
            htg[z] = list(base_h)
            hp[z] = list(base_a)
        meta["preheat_lead_h"] = 1.0

    elif strategy_id == "flat_24_7":
        for z in zones:
            htg[z] = [FLAT_HTG_C] * 24
            hp[z] = [1.0] * 24
        meta["unocc_htg_sp_f"] = FLAT_HTG_C * 9 / 5 + 32

    elif strategy_id == "deep_setback":
        for z in zones:
            htg[z] = [OCC_HTG_C if 7 <= h < 16 else DEEP_SETBACK_C for h in range(24)]
            hp[z] = [1.0 if 5 <= h < 16 else 0.0 for h in range(24)]
        meta["unocc_htg_sp_f"] = DEEP_SETBACK_C * 9 / 5 + 32
        meta["preheat_lead_h"] = 2.0

    elif strategy_id == "morning_all_on":
        for z in zones:
            htg[z] = [OCC_HTG_C if 5 <= h < 16 else UNOCC_HTG_C for h in range(24)]
            hp[z] = [1.0 if 5 <= h < 16 else 0.0 for h in range(24)]
        meta["preheat_lead_h"] = 2.0

    elif strategy_id == "stagger_preheat":
        # Spread Area wake-up across hours 05..10 (one hour offset per area)
        starts = [5, 6, 7, 8, 5, 6]
        meta["stagger_min"] = 60.0
        meta["preheat_lead_h"] = 2.0
        for zi, z in enumerate(zones):
            start_h = starts[zi % len(starts)]
            vals = []
            av = []
            for h in range(24):
                if start_h <= h < 16:
                    vals.append(OCC_HTG_C)
                    av.append(1.0)
                else:
                    vals.append(UNOCC_HTG_C)
                    av.append(0.0)
            htg[z] = vals
            hp[z] = av

    elif strategy_id.startswith("prbs"):
        meta["control_regime"] = "prbs"
        night = UNOCC_HTG_C
        day_opts = np.array([18.33, 19.0, 20.0, 20.0])
        for zi, z in enumerate(zones):
            zrng = np.random.default_rng(int(seed) + (zi + 1) * 9973)
            vals = [night] * 24
            av = [0.0] * 24
            h = 5
            while h < 16:
                dwell = int(zrng.integers(2, 5))
                until = min(16, h + dwell)
                sp = float(zrng.choice(day_opts))
                for hh in range(h, until):
                    vals[hh] = sp
                    av[hh] = 1.0
                h = until
            htg[z] = vals
            hp[z] = av

    else:
        raise ValueError(f"unknown strategy_id={strategy_id!r}")

    return {"htg_c": htg, "hp_on": hp, "meta": meta}


def controls_to_idf_blocks(controls: dict[str, Any]) -> tuple[dict, dict]:
    htg_blocks = {z: _blocks_from_hourly(controls["htg_c"][z]) for z in DSM_ZONES}
    avail_blocks = {z: _avail_from_hp(controls["hp_on"][z]) for z in DSM_ZONES}
    return htg_blocks, avail_blocks


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


def _cold_shoulder_days(n_cold: int = 12, n_shoulder: int = 6) -> list[date]:
    """Build weather-day list without inventing invalid calendar dates."""
    cold_pool = [
        date(2026, 1, d) for d in range(5, 32, 2)
    ] + [
        date(2026, 2, d) for d in range(2, 28, 2)
    ] + [
        date(2025, 12, d) for d in range(2, 31, 2)
    ]
    shoulder_pool = [
        date(2025, 10, d) for d in range(6, 31, 3)
    ] + [
        date(2025, 11, d) for d in range(3, 30, 3)
    ] + [
        date(2026, 3, d) for d in range(3, 31, 3)
    ]
    cold = cold_pool[: max(0, int(n_cold))]
    shoulder = shoulder_pool[: max(0, int(n_shoulder))]
    # If pools exhausted, cycle with unique keys via offset months already listed
    while len(cold) < n_cold and cold_pool:
        cold.append(cold_pool[len(cold) % len(cold_pool)])
    while len(shoulder) < n_shoulder and shoulder_pool:
        shoulder.append(shoulder_pool[len(shoulder) % len(shoulder_pool)])
    # Deduplicate preserving order
    seen: set[date] = set()
    out: list[date] = []
    for d in cold + shoulder:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def build_scenarios(
    *,
    smoke: bool = False,
    medium: bool = False,
    crossed: bool = False,
    n_weather_days: int = 40,
) -> list[dict]:
    """Paired scenarios: one baseline run per day + DSM arms.

    Modes
    -----
    - smoke: ~6 days × 1 DSM strategy (screening; underpowered)
    - medium: cold+shoulder × all strategies including PRBS
    - crossed: ≥30–60 weather days × all **deployable** strategies (no PRBS)
      + matched baselines; PRBS remains farm-only via medium/smoke cycles
    """
    if crossed:
        # 30 cold-ish + 10 shoulder ≈ 40 default; clamp to [30, 60]
        n = max(30, min(60, int(n_weather_days)))
        n_cold = max(20, n - 10)
        n_shoulder = n - n_cold
        days = _cold_shoulder_days(n_cold, n_shoulder)[:n]
        # Deployable strategies only — PRBS is farm/research-only
        deployable = [
            s
            for s in STRATEGY_IDS
            if s != "baseline" and not str(s).startswith("prbs")
        ]
        day_strategies = {d: list(deployable) for d in days}
    elif smoke:
        days = _cold_shoulder_days(4, 2)  # 6 days
        # one DSM strategy per day → 6 baseline + 6 dsm = 12
        dsm_cycle = [
            "stagger_preheat",
            "flat_24_7",
            "deep_setback",
            "morning_all_on",
            "prbs_z0",
            "prbs_z1",
        ]
        day_strategies = {d: [dsm_cycle[i]] for i, d in enumerate(days)}
    elif medium:
        days = _cold_shoulder_days(12, 6)
        strats = list(STRATEGY_IDS)
        strats = [s for s in strats if s != "baseline"] + [f"prbs_z{i}" for i in range(4)]
        day_strategies = {d: list(strats) for d in days}
    else:
        days = _cold_shoulder_days(4, 2)
        day_strategies = {d: ["stagger_preheat"] for d in days}

    scenarios: list[dict] = []
    for d in days:
        base = {
            "day": d.isoformat(),
            "begin": d,
            "end": d,
            "arm": "baseline",
            "strategy_id": "baseline",
            "control_regime": "baseline",
            "pair_id": f"{d.isoformat()}__baseline",
            "scenario_id": f"{d.isoformat()}_baseline",
        }
        base["seed"] = stable_seed_from_scenario(base)
        scenarios.append(base)
        for sid in day_strategies[d]:
            sc = {
                "day": d.isoformat(),
                "begin": d,
                "end": d,
                "arm": "dsm",
                "strategy_id": sid,
                "control_regime": control_regime_for(sid),
                "pair_id": f"{d.isoformat()}__{sid}",
                "scenario_id": f"{d.isoformat()}_{sid}",
            }
            sc["seed"] = stable_seed_from_scenario(sc)
            scenarios.append(sc)
    return scenarios


def pair_integrity_hashes(scenarios: list[dict]) -> dict[str, Any]:
    """Summarize pair coverage for promote / farm manifests."""
    by_day: dict[str, set[str]] = {}
    for sc in scenarios:
        by_day.setdefault(str(sc["day"]), set()).add(str(sc["arm"]))
    both = [d for d, arms in by_day.items() if "baseline" in arms and "dsm" in arms]
    return {
        "n_scenarios": len(scenarios),
        "n_days": len(by_day),
        "n_days_with_both_arms": len(both),
        "n_baseline": sum(1 for s in scenarios if s["arm"] == "baseline"),
        "n_dsm": sum(1 for s in scenarios if s["arm"] == "dsm"),
        "prbs_farm_only": True,
    }


def _quarter_index(stamp: str) -> tuple[int, int, int]:
    """hour_ending_int (1..24), minute, quarter_index 0..95 — via canonical interval15."""
    from interval15 import from_eplus_stamp

    return from_eplus_stamp(stamp)


def _control_at_hour(controls: dict[str, Any], hour_0_23: int) -> dict[str, float]:
    h = max(0, min(23, hour_0_23))
    out: dict[str, float] = {}
    for z in DSM_ZONES:
        short = ZONE_SHORT[z]
        out[f"hp_on_{short}"] = float(controls["hp_on"][z][h])
        out[f"htg_sp_{short}_c"] = float(controls["htg_c"][z][h])
        out[f"htg_sp_{short}_f"] = float(controls["htg_c"][z][h]) * 9 / 5 + 32
        out[f"occ_frac_{short}"] = float(controls["hp_on"][z][h])
    return out


def rows_from_timestep(
    ts: pd.DataFrame,
    *,
    scenario: dict,
    run_id: str,
    input_hash_hex: str,
    idf_sha: str,
    epw_sha: str,
    run_model_hash: str,
    controls: dict[str, Any],
) -> list[dict]:
    d = scenario["day"]
    dt = date.fromisoformat(d)
    year = dt.year
    ts = attach_utc_timestamps(ts, year_hint=year)
    meta = controls["meta"]
    rows = []
    seen_stamps: set[str] = set()
    for _, r in ts.iterrows():
        stamp = str(r["eplus_stamp"])
        if stamp in seen_stamps:
            continue
        seen_stamps.add(stamp)
        he, minute, q = _quarter_index(stamp)
        # control hour: use floor of interval end
        ctrl_h = 0 if he == 24 else (he - 1 if minute == 0 else he)
        if he == 24:
            ctrl_h = 23
        elif minute == 0:
            ctrl_h = (he - 1) % 24
        else:
            ctrl_h = he % 24
        ctrl = _control_at_hour(controls, ctrl_h)
        row = {
            "day": d,
            "pair_id": scenario["pair_id"],
            "arm": scenario["arm"],
            "strategy_id": scenario["strategy_id"],
            "control_regime": scenario["control_regime"],
            "scenario_id": scenario["scenario_id"],
            "run_id": run_id,
            "simulation_id": run_id,
            "input_hash": input_hash_hex,
            "run_model_hash": run_model_hash,
            "eplus_stamp": stamp,
            "timestamp_utc": r.get("timestamp_utc"),
            "hour_ending": int(he if he != 0 else 24),
            "minute": int(minute),
            "quarter_index": int(q),
            "month": dt.month,
            "doy": int(dt.timetuple().tm_yday),
            "is_weekend": 1.0 if dt.weekday() >= 5 else 0.0,
            "occupied": 1.0 if 7 <= (he % 24 if he < 24 else 0) < 16 else 0.0,
            "facility_kw": float(r["site_electric_proxy_kw"]),
            "heat_cop_proxy": 3.5,
            "cool_cop_proxy": 4.5,
            "provenance": PROVENANCE,
            "honesty": HONESTY,
            "physics_family": PHYSICS_FAMILY,
            "physics": PHYSICS_DETAIL,
            "idf_sha256": idf_sha,
            "epw_sha256": epw_sha,
            "schema_version": SCHEMA_VERSION,
            "oat_f": float(r["oat_f"]) if "oat_f" in r and pd.notna(r["oat_f"]) else np.nan,
            "rh_pct": float(r["rh_pct"]) if "rh_pct" in r and pd.notna(r["rh_pct"]) else np.nan,
            "ghi": float(r["ghi"]) if "ghi" in r and pd.notna(r["ghi"]) else np.nan,
            "weather_source": (
                "eplus_run_export"
                if ("oat_f" in r and pd.notna(r["oat_f"]))
                else "pending_attach"
            ),
            "preheat_lead_h": float(meta.get("preheat_lead_h", 0.0)),
            "stagger_min": float(meta.get("stagger_min", 0.0)),
            "unocc_htg_sp_f": float(meta.get("unocc_htg_sp_f", 65.0)),
            "occ_htg_sp_f": float(meta.get("occ_htg_sp_f", 68.0)),
            **ctrl,
        }
        for col in ZONE_TEMP_COLS.values():
            row[col] = float(r[col]) if col in r and pd.notna(r[col]) else np.nan
        rows.append(row)
    return rows


def _patch_idf_for_scenario(
    base_text: str, scenario: dict, controls: dict, *, pre_roll_days: int = 0
) -> str:
    htg_blocks, avail_blocks = controls_to_idf_blocks(controls)
    text = ensure_per_area_dsm_schedules(
        base_text,
        htg_blocks_by_zone=htg_blocks,
        avail_blocks_by_zone=avail_blocks,
    )
    d0: date = scenario["begin"]
    pre = max(0, int(pre_roll_days))
    begin = d0 - timedelta(days=pre) if pre else d0
    text = patch_run_period(
        text,
        begin_month=begin.month,
        begin_day=begin.day,
        end_month=d0.month,
        end_day=d0.day,
        begin_year=begin.year,
        end_year=d0.year,
        name=f"DSM_{d0.isoformat()}_{scenario['arm']}_pr{pre}",
    )
    return text


def filter_rows_to_evaluation_day(rows: list[dict], eval_day: str) -> list[dict]:
    """Keep only rows whose ``day`` equals the evaluation day (drop pre-roll)."""
    return [r for r in rows if str(r.get("day")) == str(eval_day)]


def _day_profile_key(df: pd.DataFrame) -> pd.Series:
    """Fingerprint facility_kw path for duplicate detection."""
    def _one(g: pd.DataFrame) -> str:
        kw = g.sort_values(["quarter_index", "hour_ending"])["facility_kw"].to_numpy(dtype=float)
        return hashlib.sha256(kw.tobytes()).hexdigest()[:16]

    return df.groupby(["arm", "day", "strategy_id"], sort=False).apply(
        lambda g: _one(g), include_groups=False
    )


def dedupe_day_profiles(farm: pd.DataFrame) -> pd.DataFrame:
    """Keep first unique day-profile per (arm, day, strategy_id)."""
    if farm.empty:
        return farm
    keys = []
    keep_idx = []
    seen: set[tuple] = set()
    for (arm, day, sid), g in farm.groupby(["arm", "day", "strategy_id"], sort=False):
        kw = g.sort_values(["quarter_index", "hour_ending"])["facility_kw"].to_numpy(dtype=float)
        sig = hashlib.sha256(kw.tobytes()).hexdigest()
        key = (arm, day, sid, sig)
        # uniqueness: one profile per arm+day+strategy (already one group); also
        # drop if identical profile reused under same arm+day+strategy via resume bugs
        group_key = (arm, day, sid)
        if group_key in seen:
            continue
        seen.add(group_key)
        keep_idx.extend(g.index.tolist())
        keys.append(key)
    return farm.loc[sorted(set(keep_idx))].reset_index(drop=True)


def assert_training_gate(farm: pd.DataFrame, manifests: dict[str, dict]) -> None:
    """Every row reconciles to a unique accepted manifest + run_model_hash."""
    if farm.empty:
        raise ValueError("empty farm")
    for col in ("input_hash", "run_model_hash", "run_id", "facility_kw", *ML_ZONE_TEMP_COLS):
        if col not in farm.columns:
            raise ValueError(f"training gate: missing column {col}")
    for h, sub in farm.groupby("input_hash"):
        if h not in manifests:
            raise ValueError(f"row input_hash {h} has no accepted manifest")
        man = manifests[h]
        if not man.get("accepted"):
            raise ValueError(f"manifest {h} not accepted")
        rmh = set(sub["run_model_hash"].astype(str).unique())
        if len(rmh) != 1:
            raise ValueError(f"input_hash {h} maps to multiple run_model_hash={rmh}")
        if man.get("run_model_hash") and man["run_model_hash"] not in rmh:
            raise ValueError(f"manifest run_model_hash mismatch for {h}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--smoke", action="store_true", help="~12 paired runs (6 days × baseline+dsm)")
    ap.add_argument("--medium", action="store_true", help="full cold+shoulder × strategies")
    ap.add_argument(
        "--crossed",
        action="store_true",
        help="Crossed farm: 30–60 weather days × deployable strategies (no PRBS); matched baselines",
    )
    ap.add_argument(
        "--n-weather-days",
        type=int,
        default=40,
        help="With --crossed: weather day count (clamped 30–60)",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=_APP / "archive" / "ml" / "artifacts" / f"{OUT_STEM}.parquet",
    )
    ap.add_argument(
        "--pre-roll-days",
        type=int,
        default=0,
        choices=(0, 3, 7, 14),
        help="Simulate N days before evaluation day; only eval-day rows are kept",
    )
    ap.add_argument(
        "--allow-weather-fallback",
        action="store_true",
        help="STRUCTURAL_DIAGNOSTIC only: allow oat=25/rh=50/ghi=0 placeholders (never promotable)",
    )
    args = ap.parse_args(argv)
    if not args.smoke and not args.medium and not args.crossed:
        args.smoke = True
    if args.crossed and (args.smoke or args.medium):
        raise SystemExit("choose one of --smoke / --medium / --crossed")

    os.environ.setdefault(
        "LAKESIDE_SITE_ROOT",
        r"C:\Users\ben\OneDrive\Desktop\testing\sp_creekside",
    )
    root = site_root()
    idf_src = _eligible_idf(root)
    epw = root / "eplus" / "weather" / "madison_amy_202508_202607.epw"
    farm_root = root / "eplus" / "dsm_farm_paired"
    farm_root.mkdir(parents=True, exist_ok=True)
    index_path = farm_root / "farm_index.jsonl"

    base_text = idf_src.read_text(encoding="utf-8")
    idf_sha = sha256_file(idf_src)
    epw_sha = sha256_file(epw)
    scenarios = build_scenarios(
        smoke=args.smoke,
        medium=args.medium,
        crossed=args.crossed,
        n_weather_days=args.n_weather_days,
    )
    integrity = pair_integrity_hashes(scenarios)
    print(
        f"paired farm scenarios={len(scenarios)} "
        f"baseline={integrity['n_baseline']} "
        f"dsm={integrity['n_dsm']} days={integrity['n_days']} "
        f"mode={'crossed' if args.crossed else 'medium' if args.medium else 'smoke'} "
        f"idf={idf_src.name}",
        flush=True,
    )
    (farm_root / "pair_integrity.json").write_text(
        json.dumps(
            {
                **integrity,
                "idf_sha256": idf_sha,
                "epw_sha256": epw_sha,
                "physics_family": PHYSICS_FAMILY,
                "physics": PHYSICS_DETAIL,
                "pre_roll_days": int(args.pre_roll_days),
                "blocked_operational_until_hourly_gate_or_waiver": True,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    # Cache accepted timestep frames by input_hash for pair expansion
    run_cache: dict[str, dict] = {}
    accepted = 0
    rejected = 0
    manifests: dict[str, dict] = {}

    for sc in scenarios:
        controls = build_area_controls(sc["strategy_id"], sc["seed"])
        text = _patch_idf_for_scenario(
            base_text, sc, controls, pre_roll_days=int(args.pre_roll_days)
        )
        scen_hash = input_hash(text, sc)
        run_id = f"{sc['scenario_id'].replace(':', '')}_{scen_hash[:12]}"
        run_dir = farm_root / f"{run_id}"
        man_path = run_dir / "run_manifest.json"
        ts_path = run_dir / "timestep_proxy_mat.parquet"

        if man_path.is_file() and ts_path.is_file():
            man = json.loads(man_path.read_text(encoding="utf-8"))
            if man.get("accepted") and man.get("input_hash") == scen_hash:
                ts = pd.read_parquet(ts_path)
                run_model_hash = man.get("run_model_hash") or sha256_file(run_dir / "model.idf")
                run_cache[scen_hash] = {
                    "scenario": sc,
                    "controls": controls,
                    "ts": ts,
                    "run_id": run_id,
                    "input_hash": scen_hash,
                    "run_model_hash": run_model_hash,
                    "manifest": man,
                }
                manifests[scen_hash] = man
                accepted += 1
                print(f"RESUME {run_id}", flush=True)
                continue

        if run_dir.exists():
            shutil.rmtree(run_dir, ignore_errors=True)
        run_dir.mkdir(parents=True)
        idf_path = run_dir / "model.idf"
        idf_path.write_text(text, encoding="utf-8")
        run_model_hash = sha256_file(idf_path)

        try:
            man_obj = run_energyplus(
                run_id=run_id,
                scenario_id=sc["scenario_id"],
                idf_path=idf_path,
                epw_path=epw,
                output_dir=run_dir / "sim",
                require_zero_severe=True,
                allow_staged_idf=True,
            )
        except FileNotFoundError as e:
            print(
                f"EnergyPlus missing or path error: {e}\n"
                f"Install EnergyPlus and/or set eplus_native.DEFAULT_EPLUS_EXE.\n"
                f"Then: python -u scripts/eplus_heating_dsm_farm.py --smoke",
                file=sys.stderr,
            )
            return 2

        man = man_obj.to_dict()
        man["input_hash"] = scen_hash
        man["run_model_hash"] = run_model_hash
        man["arm"] = sc["arm"]
        man["pair_id"] = sc["pair_id"]
        man["strategy_id"] = sc["strategy_id"]
        man["control_regime"] = sc["control_regime"]
        man["seed"] = sc["seed"]
        (run_dir / "run_manifest.json").write_text(
            json.dumps(man, indent=2) + "\n", encoding="utf-8"
        )
        with index_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(man) + "\n")

        if not man_obj.accepted:
            rejected += 1
            print(f"REJECT {run_id}: {man_obj.reject_reasons}", flush=True)
            continue

        try:
            ts = load_timestep_proxy_and_mat(run_dir / "sim", interval_hours=0.25)
            ts = filter_stamps_for_day(ts, sc["day"])
            ts = ts.drop_duplicates(subset=["eplus_stamp"], keep="last").reset_index(drop=True)
            if ts.empty:
                raise ValueError("no run-period stamps after design-day filter")
            ts.to_parquet(ts_path, index=False)
        except Exception as e:
            rejected += 1
            print(f"EXTRACT FAIL {run_id}: {e}", flush=True)
            continue

        accepted += 1
        manifests[scen_hash] = man
        run_cache[scen_hash] = {
            "scenario": sc,
            "controls": controls,
            "ts": ts,
            "run_id": run_id,
            "input_hash": scen_hash,
            "run_model_hash": run_model_hash,
            "manifest": man,
        }
        print(f"OK {run_id} timesteps={len(ts)} arm={sc['arm']} sid={sc['strategy_id']}", flush=True)

    if accepted == 0:
        print("NO ACCEPTED RUNS — farm failed closed", file=sys.stderr)
        return 1

    # Expand paired rows: each DSM pair_id gets matching baseline rows + dsm rows
    by_day_baseline: dict[str, dict] = {}
    dsm_runs: list[dict] = []
    for payload in run_cache.values():
        sc = payload["scenario"]
        if sc["arm"] == "baseline":
            by_day_baseline[sc["day"]] = payload
        else:
            dsm_runs.append(payload)

    all_rows: list[dict] = []
    # Also keep standalone baseline arm rows (pair_id …__baseline) for provenance
    for day, payload in by_day_baseline.items():
        rows = rows_from_timestep(
            payload["ts"],
            scenario=payload["scenario"],
            run_id=payload["run_id"],
            input_hash_hex=payload["input_hash"],
            idf_sha=idf_sha,
            epw_sha=epw_sha,
            run_model_hash=payload["run_model_hash"],
            controls=payload["controls"],
        )
        all_rows.extend(filter_rows_to_evaluation_day(rows, day))

    for payload in dsm_runs:
        sc = payload["scenario"]
        day = sc["day"]
        base = by_day_baseline.get(day)
        if base is None:
            print(f"WARN no baseline for day {day}; skipping pair {sc['pair_id']}", flush=True)
            continue
        # Paired baseline copy under DSM pair_id — strategy_id is the matched DSM
        # so (arm, day, strategy_id) uniquely identifies one 96-step profile.
        base_sc = dict(base["scenario"])
        base_sc["pair_id"] = sc["pair_id"]
        base_sc["arm"] = "baseline"
        base_sc["strategy_id"] = sc["strategy_id"]
        base_sc["control_regime"] = sc["control_regime"]
        all_rows.extend(
            filter_rows_to_evaluation_day(
                rows_from_timestep(
                    base["ts"],
                    scenario=base_sc,
                    run_id=base["run_id"],
                    input_hash_hex=base["input_hash"],
                    idf_sha=idf_sha,
                    epw_sha=epw_sha,
                    run_model_hash=base["run_model_hash"],
                    controls=base["controls"],
                ),
                day,
            )
        )
        all_rows.extend(
            filter_rows_to_evaluation_day(
                rows_from_timestep(
                    payload["ts"],
                    scenario=sc,
                    run_id=payload["run_id"],
                    input_hash_hex=payload["input_hash"],
                    idf_sha=idf_sha,
                    epw_sha=epw_sha,
                    run_model_hash=payload["run_model_hash"],
                    controls=payload["controls"],
                ),
                day,
            )
        )

    farm = pd.DataFrame(all_rows)
    farm = dedupe_day_profiles(farm)

    # Weather attach — prefer eplus_run_export already on rows; else hourly attach.
    weather_ok = False
    if len(farm) and "weather_source" in farm.columns:
        n_ep = int((farm["weather_source"].astype(str) == "eplus_run_export").sum())
        if n_ep == len(farm) and farm["oat_f"].notna().all():
            weather_ok = True
            # RH/GHI may still be NaN — handled below
    try:
        if not weather_ok:
            from artifact_paths import weather_history_csv, demand_hourly_csv
            from site_weather import load_weather_hourly, load_hourly_demand

            wx = load_weather_hourly(weather_history_csv())
            if len(wx) and "oat_f" in wx.columns:
                w = wx[["day", "hour_ending", "oat_f"]].copy()
                w["hour_ending"] = w["hour_ending"].astype(int)
                w.loc[w["hour_ending"] == 0, "hour_ending"] = 24
                w = w.rename(columns={"oat_f": "oat_wx", "hour_ending": "_he"})
                farm["_he"] = farm["hour_ending"].astype(int)
                farm = farm.merge(w, on=["day", "_he"], how="left")
                farm["oat_f"] = farm["oat_f"].fillna(farm["oat_wx"])
                farm.drop(columns=["_he", "oat_wx"], inplace=True, errors="ignore")
                if "rh_pct" in wx.columns:
                    wr = wx[["day", "hour_ending", "rh_pct"]].copy()
                    wr["hour_ending"] = wr["hour_ending"].astype(int)
                    wr.loc[wr["hour_ending"] == 0, "hour_ending"] = 24
                    wr = wr.rename(columns={"rh_pct": "rh_wx", "hour_ending": "_he"})
                    farm["_he"] = farm["hour_ending"].astype(int)
                    farm = farm.merge(wr, on=["day", "_he"], how="left")
                    farm["rh_pct"] = farm["rh_pct"].fillna(farm["rh_wx"])
                    farm.drop(columns=["_he", "rh_wx"], inplace=True, errors="ignore")
                if "ghi" in wx.columns:
                    wg = wx[["day", "hour_ending", "ghi"]].copy()
                    wg["hour_ending"] = wg["hour_ending"].astype(int)
                    wg.loc[wg["hour_ending"] == 0, "hour_ending"] = 24
                    wg = wg.rename(columns={"ghi": "ghi_wx", "hour_ending": "_he"})
                    farm["_he"] = farm["hour_ending"].astype(int)
                    farm = farm.merge(wg, on=["day", "_he"], how="left")
                    farm["ghi"] = farm["ghi"].fillna(farm["ghi_wx"])
                    farm.drop(columns=["_he", "ghi_wx"], inplace=True, errors="ignore")
            dem = load_hourly_demand(demand_hourly_csv())
            if len(dem) and "oat_f" in dem.columns:
                m = dem[["day", "hour_ending", "oat_f"]].copy()
                m["hour_ending"] = m["hour_ending"].astype(int)
                m.loc[m["hour_ending"] == 0, "hour_ending"] = 24
                m = m.rename(columns={"oat_f": "oat_dem", "hour_ending": "_he"})
                farm["_he"] = farm["hour_ending"].astype(int)
                farm = farm.merge(m, on=["day", "_he"], how="left")
                farm["oat_f"] = farm["oat_f"].fillna(farm["oat_dem"])
                farm.drop(columns=["_he", "oat_dem"], inplace=True, errors="ignore")
            weather_ok = bool(farm["oat_f"].notna().all()) if len(farm) else False
            if weather_ok and (
                "weather_source" not in farm.columns
                or (farm["weather_source"].astype(str) == "pending_attach").any()
            ):
                farm["weather_source"] = "hourly_history_or_demand_attach"
    except Exception as e:
        if not weather_ok:
            print(f"weather attach skipped: {e}", flush=True)

    if not weather_ok:
        if args.allow_weather_fallback:
            farm["oat_f"] = farm["oat_f"].fillna(25.0)
            farm["rh_pct"] = farm["rh_pct"].fillna(50.0)
            farm["ghi"] = farm["ghi"].fillna(0.0)
            farm["weather_source"] = "STRUCTURAL_DIAGNOSTIC_FALLBACK_25_50_0"
            farm["honesty"] = "HYBRID_SCREENING"
            print(
                "WARN: weather fallback oat=25/rh=50/ghi=0 — STRUCTURAL_DIAGNOSTIC only; not promotable",
                flush=True,
            )
        else:
            print(
                "TRAINING GATE FAIL: missing farm weather (OAT). "
                "Refuse silent oat=25/rh=50/ghi=0. "
                "Pass --allow-weather-fallback only for STRUCTURAL_DIAGNOSTIC smoke.",
                file=sys.stderr,
            )
            return 1
    else:
        # RH/GHI may still be missing; fail closed unless diagnostic fallback
        if farm["rh_pct"].isna().any() or farm["ghi"].isna().any():
            if args.allow_weather_fallback:
                farm["rh_pct"] = farm["rh_pct"].fillna(50.0)
                farm["ghi"] = farm["ghi"].fillna(0.0)
            else:
                print(
                    "TRAINING GATE FAIL: missing RH/GHI on farm rows after weather attach.",
                    file=sys.stderr,
                )
                return 1

    # Training gate
    try:
        assert_training_gate(farm, manifests)
    except ValueError as e:
        print(f"TRAINING GATE FAIL: {e}", file=sys.stderr)
        return 1

    # hp_on variation check
    hp_std = {c: float(farm[c].std()) for c in HP_ON_COLS if c in farm.columns}
    if all(v < 1e-9 for v in hp_std.values()):
        print("WARN: hp_on_* have zero variance across farm", flush=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    farm.to_parquet(args.out, index=False)

    # Optional site copy
    site_out = farm_root / f"{OUT_STEM}.parquet"
    try:
        farm.to_parquet(site_out, index=False)
    except Exception as e:
        print(f"site parquet copy skipped: {e}", flush=True)

    summary = {
        "n_rows": int(len(farm)),
        "n_runs_accepted": accepted,
        "n_runs_rejected": rejected,
        "n_days": int(farm["day"].nunique()),
        "n_pair_ids": int(farm["pair_id"].nunique()),
        "arms": sorted(farm["arm"].astype(str).unique().tolist()),
        "strategies": sorted(farm["strategy_id"].astype(str).unique().tolist()),
        "control_regimes": sorted(farm["control_regime"].astype(str).unique().tolist()),
        "provenance": PROVENANCE,
        "honesty": HONESTY,
        "schema_version": SCHEMA_VERSION,
        "idf_sha256": idf_sha,
        "epw_sha256": epw_sha,
        "staged_idf": str(idf_src),
        "out": str(args.out),
        "site_out": str(site_out),
        "farm_root": str(farm_root),
        "hp_on_std": hp_std,
        "absolute_targets": ["facility_kw", *ML_ZONE_TEMP_COLS],
        "notes": (
            "Paired native EnergyPlus IdealLoads+COP + 6-area MAT. "
            "PRBS uses control_regime=prbs (not stagger one-hots). "
            "E+ LST→UTC uses fixed CST−6. Canonical *_best_utility.idf never overwritten."
        ),
    }
    summary_path = args.out.parent / f"{OUT_STEM}_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (farm_root / f"{OUT_STEM}_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
