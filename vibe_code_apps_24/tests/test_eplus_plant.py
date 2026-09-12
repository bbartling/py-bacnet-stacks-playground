"""EnergyPlusPlant streams vibe23 day results (mocked runner)."""

from pathlib import Path

import numpy as np
import pandas as pd

from vibe24.eplus_plant import CLAIM_ENERGYPLUS, EnergyPlusPlant


def test_eplus_plant_advances_from_mock_day(monkeypatch, tmp_path: Path):
    n = 288
    zone = np.linspace(78.0, 70.0, n)
    kw = np.where(zone > 73.0, 2.5, 0.4)
    frame = pd.DataFrame(
        {
            "timestamp": [f"07/15 {i // 12:02d}:{(i % 12) * 5:02d}:00" for i in range(n)],
            "facility_kw": kw,
            "zone_temp_f": zone,
            "hvac_kw": kw,
        }
    )

    def fake_run(*_a, **_k):
        out = Path(_k["output_dir"])
        out.mkdir(parents=True, exist_ok=True)
        (out / "eplusout.csv").write_text("x\n", encoding="utf-8")
        return {
            "soft_ok": True,
            "fatal_count": 0,
            "severe_count": 0,
            "energyplus_version": "fake-26.1",
        }

    monkeypatch.setattr("vibe23.residential.runner.run_residential_day", fake_run)
    monkeypatch.setattr("vibe23.residential.runner.parse_eplus_csv", lambda _p: frame)
    monkeypatch.setattr(
        "vibe23.residential.model.find_denver_epw",
        lambda *_a, **_k: tmp_path / "x.epw",
    )
    (tmp_path / "x.epw").write_text("hdr\n" * 8 + "2026,7,15,1,0,?,25.0\n", encoding="utf-8")

    plant = EnergyPlusPlant(month=7, day=15, run_root=tmp_path / "runs")
    plant.reset(oa_f=85.0, zone_f=78.0)
    first = plant.step(0.0, {"ZONE-SP": 72.0, "DEADBAND": 2.0, "HEAT-EFF": 71.0, "COOL-EFF": 73.0, "UNIT-ENABLE": 1.0})
    assert first["ZONE-T"] == zone[0]
    assert plant.claim == CLAIM_ENERGYPLUS

    later = plant.step(5.0 / 60.0, {"ZONE-SP": 72.0, "DEADBAND": 2.0, "HEAT-EFF": 71.0, "COOL-EFF": 73.0, "UNIT-ENABLE": 1.0})
    assert later["ZONE-T"] == zone[1]
    assert later["FAN-S"] in (0.0, 1.0)
