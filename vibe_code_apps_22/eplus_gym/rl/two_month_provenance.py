"""Freeze inputs for two-month frozen-policy replay."""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eplus_gym.a04_identity import A04_IDF_NAME
from eplus_gym.rl.research_spaces import decode_discrete_research_v3
from eplus_gym.rl.two_month_calendar import FIRST_SCORED_DAY, LAST_SCORED_DAY, LOOKBACK_DAY, scored_days
from eplus_gym.site_pins import resolve_site_epw, sha256_file

PUBLIC_LABELS = [
    "RETROSPECTIVE ENERGYPLUS POLICY SCREENING",
    "A04 NOT TRANSIENT-VALIDATED",
    "VERIFIED BAS INCUMBENT UNRESOLVED",
    "ILLUSTRATIVE TARIFFS",
    "NO OPERATIONAL DSM AUTHORITY",
    "NO BACNET COMMAND AUTHORITY",
    "RETROSPECTIVE_CONTAMINATED",
    "NO PRISTINE LOCKED TEST",
]

UTILITY_ACCOUNT = "CS 351075"
NOT_AVAILABLE = "NOT_AVAILABLE_FROM_SOURCE_INVOICE"

PPO_ZIP_REL = (
    "reports/eplus_gym/rl/research_long_flat_plus_demand_20260820T132506Z/"
    "ppo_seed0/models/ppo_final.zip"
)
DQN_ZIP_REL = (
    "reports/eplus_gym/rl/research_long_illustrative_tou_plus_demand_20260820T210304Z/"
    "dqn_seed1/models/dqn_final.zip"
)


def _read_utility_rows(site: Path) -> list[dict[str, Any]]:
    path = site / "utilities" / "utility_bills_raw.csv"
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [r for r in rows if str(r.get("account", "")).strip() == UTILITY_ACCOUNT]


def load_actual_utility_evidence(site: Path) -> dict[str, Any]:
    rows = _read_utility_rows(site)
    by_period = {str(r["billing_period"]): r for r in rows}
    dec = by_period.get("202512")
    jan = by_period.get("202601")
    if not dec or not jan:
        raise ValueError("missing Dec 2025 or Jan 2026 utility rows for CS 351075")

    def _f(row: dict, key: str) -> float:
        return float(row[key])

    dec_kwh = _f(dec, "kwh")
    jan_kwh = _f(jan, "kwh")
    dec_bill = _f(dec, "meter_cost_usd")
    jan_bill = _f(jan, "meter_cost_usd")
    return {
        "account": UTILITY_ACCOUNT,
        "source_path": str(site / "utilities" / "utility_bills_raw.csv"),
        "dec_2025": {
            "kwh": dec_kwh,
            "billed_demand_kw": _f(dec, "billed_demand_kw"),
            "actual_total_bill_usd": dec_bill,
            "actual_energy_charge_usd": NOT_AVAILABLE,
            "actual_demand_charge_usd": NOT_AVAILABLE,
        },
        "jan_2026": {
            "kwh": jan_kwh,
            "billed_demand_kw": _f(jan, "billed_demand_kw"),
            "actual_total_bill_usd": jan_bill,
            "actual_energy_charge_usd": NOT_AVAILABLE,
            "actual_demand_charge_usd": NOT_AVAILABLE,
        },
        "two_month": {
            "kwh": dec_kwh + jan_kwh,
            "actual_total_bill_usd": dec_bill + jan_bill,
        },
        "invoice_line_item_note": (
            "Verified invoice line-item energy/demand charge decomposition was not available. "
            "Actual total bill is shown without fabricating a component split."
        ),
    }


def build_provenance(*, app_root: Path, site: Path) -> dict[str, Any]:
    from eplus_gym.mega.tariff_modes import default_tariff_catalog

    idf = app_root / "models" / "eplus" / A04_IDF_NAME
    epw = resolve_site_epw(site)
    ppo_zip = site / PPO_ZIP_REL.replace("/", "\\").replace("\\", "/")
    if not ppo_zip.is_file():
        ppo_zip = site / PPO_ZIP_REL
    dqn_zip = site / DQN_ZIP_REL
    contracts = {
        "observed_bas_incumbent_v2": app_root / "contracts/observed_bas_incumbent_v2.json",
        "baseline_terminology_v1": app_root / "contracts/baseline_terminology_v1.json",
        "verified_bas_incumbent_v1": app_root / "contracts/verified_bas_incumbent_v1.json",
    }
    flat = default_tariff_catalog()["flat_illustrative"]
    tou = default_tariff_catalog()["tou_evening_peak_illustrative"]
    d42 = decode_discrete_research_v3(42, day=FIRST_SCORED_DAY)
    d43 = decode_discrete_research_v3(43, day=FIRST_SCORED_DAY)
    utility = load_actual_utility_evidence(site)
    return {
        "schema": "vibe22.two_month_provenance.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "public_labels": PUBLIC_LABELS,
        "calendar": {
            "lookback_day": LOOKBACK_DAY,
            "first_scored_day": FIRST_SCORED_DAY,
            "last_scored_day": LAST_SCORED_DAY,
            "scored_days": len(scored_days()),
            "expected_intervals": len(scored_days()) * 96,
        },
        "idf": {"path": str(idf), "sha256": sha256_file(idf)},
        "epw": {"path": str(epw), "sha256": sha256_file(epw)},
        "policies": {
            "ppo_flat": {"path": str(ppo_zip), "sha256": sha256_file(ppo_zip) if ppo_zip.is_file() else None},
            "dqn_tou": {"path": str(dqn_zip), "sha256": sha256_file(dqn_zip) if dqn_zip.is_file() else None},
        },
        "obs_action": {
            "obs_schema": "vibe22.obs.v4.mega",
            "observation_dim": 206,
            "action_contract_version": "research_action_contract_v3",
            "forecast_source": "PERFECT_EPISODE_FORECAST_RETROSPECTIVE",
        },
        "contracts": {k: {"path": str(p), "sha256": sha256_file(p)} for k, p in contracts.items()},
        "grid_policies": {
            "discrete_42": {
                "occupied_heating_f": d42.occupied_heating_f,
                "unoccupied_heating_f": d42.unoccupied_heating_f,
                "recovery_lead_minutes": d42.recovery_lead_minutes,
                "post_occupancy_extension_minutes": d42.post_occupancy_extension_minutes,
            },
            "discrete_43": {
                "occupied_heating_f": d43.occupied_heating_f,
                "unoccupied_heating_f": d43.unoccupied_heating_f,
                "recovery_lead_minutes": d43.recovery_lead_minutes,
                "post_occupancy_extension_minutes": d43.post_occupancy_extension_minutes,
            },
        },
        "tariffs": {
            "ILLUSTRATIVE_FLAT_PLUS_DEMAND": {
                "energy_rate_usd_per_kwh": flat.energy_rate_per_kwh,
                "demand_rate_usd_per_kw": flat.demand_rate_per_kw,
                "ratchet_floor_kw": 0.0,
                "contract_demand_floor_kw": 0.0,
                "floor_disclosure": "Unverified ratchet/contract floors use zero for illustrative scenario.",
            },
            "ILLUSTRATIVE_TOU_PLUS_DEMAND": {
                "demand_rate_usd_per_kw": tou.demand_rate_per_kw,
                "ratchet_floor_kw": 0.0,
                "contract_demand_floor_kw": 0.0,
            },
        },
        "utility_evidence": utility,
        "energyplus_version": "26.1.0",
        "bacnet_commands": 0,
    }
