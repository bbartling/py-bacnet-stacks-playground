"""Named tariff experiments FLAT_PLUS_DEMAND / ILLUSTRATIVE_TOU_PLUS_DEMAND."""
from __future__ import annotations

from eplus_gym.mega.tariff_modes import (
    ILLUSTRATIVE_TARIFF_BANNER,
    build_tariff_forecast_vectors,
    default_tariff_catalog,
    experiment_id_for_mode,
    resolve_tariff_mode,
    tariff_banner,
    tariff_mode_mask,
)


def test_flat_plus_demand_alias():
    assert resolve_tariff_mode("FLAT_PLUS_DEMAND") == "flat_illustrative"
    vec = build_tariff_forecast_vectors("FLAT_PLUS_DEMAND")
    assert len(vec["next_96x15min_energy_rates"]) == 96
    assert len(set(vec["next_96x15min_energy_rates"])) == 1
    assert vec["demand_rate_per_kw"] == 12.0
    assert vec["experiment_id"] == "FLAT_PLUS_DEMAND"


def test_illustrative_tou_plus_demand():
    vec = build_tariff_forecast_vectors("ILLUSTRATIVE_TOU_PLUS_DEMAND")
    rates = vec["next_96x15min_energy_rates"]
    assert len(rates) == 96
    assert max(rates) > min(rates)
    assert ILLUSTRATIVE_TARIFF_BANNER in (vec["banner"] or "")
    assert experiment_id_for_mode("ILLUSTRATIVE_TOU_PLUS_DEMAND") == "ILLUSTRATIVE_TOU_PLUS_DEMAND"


def test_obs_mask_stable_six_modes():
    m = tariff_mode_mask("FLAT_PLUS_DEMAND")
    assert m.shape == (6,)
    assert float(m.sum()) == 1.0
    assert float(tariff_mode_mask("flat_illustrative").sum()) == 1.0


def test_catalog_contains_experiments():
    cat = default_tariff_catalog()
    assert "FLAT_PLUS_DEMAND" in cat
    assert "ILLUSTRATIVE_TOU_PLUS_DEMAND" in cat
    assert tariff_banner("ILLUSTRATIVE_TOU_PLUS_DEMAND") == ILLUSTRATIVE_TARIFF_BANNER
