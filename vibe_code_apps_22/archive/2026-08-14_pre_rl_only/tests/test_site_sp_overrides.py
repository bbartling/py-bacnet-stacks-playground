"""Site Config heating SP overrides for RuleController."""
from __future__ import annotations

from eplus_gym.controllers import RuleController, effective_htg_setpoints_f


def test_site_config_overrides_baseline_unocc():
    eff = effective_htg_setpoints_f(
        "baseline", occ_htg_sp_f=70.0, unocc_htg_sp_f=55.0
    )
    assert eff["occ_htg_sp_f"] == 70.0
    assert eff["unocc_htg_sp_f"] == 55.0
    ctrl = RuleController("baseline", occ_htg_sp_f=70.0, unocc_htg_sp_f=55.0)
    series = ctrl.series_f()
    assert min(series) == 55.0
    assert max(series) == 70.0


def test_deep_setback_is_5f_below_site_unocc():
    eff = effective_htg_setpoints_f(
        "deep_setback", occ_htg_sp_f=70.0, unocc_htg_sp_f=55.0
    )
    assert eff["occ_htg_sp_f"] == 70.0
    assert eff["unocc_htg_sp_f"] == 50.0
    ctrl = RuleController("deep_setback", occ_htg_sp_f=70.0, unocc_htg_sp_f=55.0)
    assert min(ctrl.series_f()) == 50.0


def test_flat_uses_occ_only():
    ctrl = RuleController("flat_24_7", occ_htg_sp_f=71.0, unocc_htg_sp_f=55.0)
    assert set(ctrl.series_f()) == {71.0}


def test_strategy_library_reflects_site_config():
    from eplus_gym_app.dsm_console import strategy_library

    lib = strategy_library(
        {
            "setpoints_f": {
                "occupied_heating_f": 70.0,
                "unoccupied_heating_f": 55.0,
            }
        }
    )
    by_id = {r["strategy_id"]: r for r in lib["rows"]}
    assert by_id["baseline"]["unocc_htg_sp_f"] == 55.0
    assert by_id["deep_setback"]["unocc_htg_sp_f"] == 50.0
    assert by_id["flat_24_7"]["unocc_htg_sp_f"] == 70.0
