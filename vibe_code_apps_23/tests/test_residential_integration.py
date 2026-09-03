from __future__ import annotations

from pathlib import Path

import pytest

from vibe23.energyplus import resolve_native_energyplus
from vibe23.residential.model import MODEL_IDF, find_denver_epw


@pytest.mark.skipif(resolve_native_energyplus() is None, reason="EnergyPlus not installed")
@pytest.mark.skipif(find_denver_epw() is None, reason="Denver-type EPW missing")
def test_residential_smoke_july(tmp_path: Path):
    from vibe23.residential.runner import run_residential_day

    result = run_residential_day(MODEL_IDF, output_dir=tmp_path / "jul", month=7, day=15)
    assert result["soft_ok"]
    assert result["fatal_count"] == 0
    assert len(result["facility_kw"]) == 288
    assert len(result["zone_temp_f"]) == 288
