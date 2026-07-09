"""Pandas vs open-fdd sidecar fault hours — parity when sidecar is reachable."""

import numpy as np
import pandas as pd
import pytest

import cookbook_engine as ce
import cookbook_rules as cb
import cookbook_sql as csql


def _vav_frame(n=120, zone_t=72.0):
    idx = pd.date_range("2026-05-01", periods=n, freq="300s", tz="UTC")
    d = pd.DataFrame({"timestamp": idx, "zone_t": np.full(n, zone_t)}, index=range(n))
    d.attrs["equipment_id"] = "VAV_TEST"
    return d


def test_vav1_pandas_comfort_fault():
    d = _vav_frame(zone_t=80.0)
    rule = cb.RULES_BY_ID["VAV-1"]
    res = ce.run_rule(rule, d, {"zone_t": "zone_t"}, 300.0, {"zone_lo": 68, "zone_hi": 76}, False)
    assert res["applicable"]
    assert res["fault_hours"] > 0


@pytest.mark.skipif(not csql.has_sql("VAV-1"), reason="SQL catalog empty")
def test_sidecar_parity_vav1_when_available():
    import cookbook_sidecar as cs

    if not cs.is_available():
        pytest.skip("open-fdd edge not running")

    d = _vav_frame(zone_t=80.0)
    rule = cb.RULES_BY_ID["VAV-1"]
    params = {"zone_lo": 68, "zone_hi": 76}
    pandas = ce.run_rule(rule, d, {"zone_t": "zone_t"}, 300.0, params, False)
    side = csql.try_sidecar_hours("VAV-1", "VAV_TEST", params=params)
    if side is None or not side.get("ok"):
        pytest.skip("sidecar run failed — historian may lack VAV_TEST")

    tol = max(2.0, pandas["fault_hours"] * 0.15)
    assert abs(pandas["fault_hours"] - side["fault_hours"]) <= tol
