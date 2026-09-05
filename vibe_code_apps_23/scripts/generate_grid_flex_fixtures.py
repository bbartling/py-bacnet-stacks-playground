"""Generate ILLUSTRATIVE 13×13 ranking + twin_export fixtures (no live EnergyPlus)."""
from __future__ import annotations

import json
from pathlib import Path

from vibe23.battery import BatteryParams, simulate_dispatch
from vibe23.residential.experiment import default_thermostat_candidates, save_ranking
from vibe23.residential.tariffs import summer_tou_hourly, winter_tou_hourly
from vibe23.residential.thermostat import build_schedule_action
from vibe23.studio.demo_data import load_season_day
from vibe23.tariff import BillingState, billing_cost

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "studio"
PARAMS = BatteryParams(
    capacity_kwh=13.5,
    max_charge_kw=5.0,
    max_discharge_kw=5.0,
    eta_c=0.95,
    eta_d=0.95,
    soc_min=0.1,
    soc_max=0.95,
    initial_soc=0.5,
)


def _scale_kw(base: list[float], pre_c: float, ev_c: float, *, winter: bool) -> list[float]:
    out: list[float] = []
    for i, kw in enumerate(base):
        hour = (i + 1) * 24.0 / len(base)
        factor = 1.0
        if winter:
            if 5 < hour <= 6:
                factor += 0.04 * (pre_c - 72.0)
            elif 6 < hour <= 9:
                factor += 0.05 * (ev_c - 72.0)
        else:
            if 13 < hour <= 16:
                factor += 0.035 * (72.0 - pre_c)
            elif 16 < hour <= 21:
                factor += 0.04 * (ev_c - 72.0)
        out.append(max(0.05, kw * factor))
    return out


def _comfort(pre_c: float, ev_c: float) -> bool:
    for c in (pre_c, ev_c):
        if c - 1.0 < 69.5 - 1e-9 or c + 1.0 > 74.5 + 1e-9:
            return False
    return True


def build_season(season: str) -> None:
    winter = season == "winter"
    day = load_season_day(season)
    base_kw = list(day["baseline_kw"])
    base_temp = list(day["baseline_temp_f"])
    tariff = winter_tou_hourly() if winter else summer_tou_hourly()
    prices = list(tariff.energy_rates_per_kwh)
    opening = BillingState()
    mode = "winter_dr" if winter else "summer_dr"

    def score(kw: list[float]) -> tuple[float, list[float], list[float]]:
        dispatch = simulate_dispatch(kw, prices, PARAMS, mode="price_arbitrage")
        purchased = list(dispatch["purchased_kw"])  # type: ignore[arg-type]
        soc = list(dispatch["soc"])  # type: ignore[arg-type]
        bill = billing_cost(purchased, tariff=tariff, opening_state=opening)
        return float(bill["total_cost_usd"]), purchased, soc

    base_cost, base_purchased, base_soc = score(base_kw)
    thermal_base = float(billing_cost(base_kw, tariff=tariff, opening_state=opening)["total_cost_usd"])
    rows: list[dict] = [
        {
            "candidate_id": "BASELINE",
            "billing_cost": base_cost,
            "thermal_cost": thermal_base,
            "peak_kw": float(max(base_kw)),
            "total_kwh": float(sum(v / 12.0 for v in base_kw)),
            "comfort_ok": True,
            "soft_ok": True,
            "wall_seconds": 0.8,
            "action_json": json.dumps({"mode": "baseline", "pre_center_f": 72.0, "event_center_f": 72.0}),
            "idf_sha256": "0" * 64,
            "attach_battery": True,
            "pre_center_f": 72.0,
            "event_center_f": 72.0,
            "note": "ILLUSTRATIVE_FIXTURE",
        }
    ]

    for cand in default_thermostat_candidates(season=season):
        action = build_schedule_action(mode=mode, **dict(cand.action))
        pre_c = float(action["pre_center_f"])
        ev_c = float(action["event_center_f"])
        kw = _scale_kw(base_kw, pre_c, ev_c, winter=winter)
        ok = _comfort(pre_c, ev_c)
        if ok:
            cost, _purchased, _soc = score(kw)
            thermal = float(billing_cost(kw, tariff=tariff, opening_state=opening)["total_cost_usd"])
        else:
            cost = float("inf")
            thermal = float("inf")
        rows.append(
            {
                "candidate_id": cand.candidate_id,
                "billing_cost": cost,
                "thermal_cost": thermal,
                "peak_kw": float(max(kw)),
                "total_kwh": float(sum(v / 12.0 for v in kw)),
                "comfort_ok": ok,
                "soft_ok": True,
                "wall_seconds": 0.75,
                "action_json": json.dumps(action, sort_keys=True),
                "idf_sha256": "0" * 64,
                "attach_battery": True,
                "pre_center_f": pre_c,
                "event_center_f": ev_c,
                "note": "ILLUSTRATIVE_FIXTURE",
            }
        )

    out = FIXTURES / f"{season}_thermostat_grid_ranking.json"
    ranking = save_ranking(
        rows,
        csv_path=FIXTURES / f"_{season}_ranking_tmp.csv",
        json_path=out,
        winner_key="billing_cost",
    )
    ranking["fixture_kind"] = "ILLUSTRATIVE_PHYSICS_PROXY"
    out.write_text(json.dumps(ranking, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (FIXTURES / f"_{season}_ranking_tmp.csv").unlink(missing_ok=True)

    winner = ranking["winner"]
    w_action = json.loads(winner["action_json"])
    if winner["candidate_id"] == "BASELINE":
        w_kw = base_kw
        w_temp = base_temp
        w_purchased, w_soc = base_purchased, base_soc
    else:
        w_kw = _scale_kw(
            base_kw,
            float(w_action["pre_center_f"]),
            float(w_action["event_center_f"]),
            winter=winter,
        )
        w_temp = list(base_temp)
        for i in range(len(w_temp)):
            hour = (i + 1) * 24.0 / len(w_temp)
            if (6 < hour <= 9) if winter else (16 < hour <= 21):
                w_temp[i] = 0.7 * w_temp[i] + 0.3 * float(w_action["event_center_f"])
        _, w_purchased, w_soc = score(w_kw)

    twin = {
        "schema": "vibe23.residential_grid_twin_export.v1",
        "fixture_kind": "ILLUSTRATIVE_PHYSICS_PROXY",
        "baseline": {
            "facility_kw": base_kw,
            "zone_temp_f": base_temp,
            "purchased_kw": base_purchased,
            "soc": base_soc,
        },
        "winner": {
            "candidate_id": winner["candidate_id"],
            "facility_kw": w_kw,
            "zone_temp_f": w_temp,
            "purchased_kw": w_purchased,
            "soc": w_soc,
            "action": w_action,
            "billing_cost": winner["billing_cost"],
        },
    }
    (FIXTURES / f"{season}_twin_export.json").write_text(
        json.dumps(twin, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(season, "rows", ranking["candidate_count"], "winner", winner["candidate_id"])


if __name__ == "__main__":
    for s in ("summer", "winter"):
        build_season(s)
    print("done")
