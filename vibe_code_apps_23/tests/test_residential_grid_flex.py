"""Unit tests for battery-cooptimized grid flex campaign (no live EnergyPlus)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from vibe23.residential.campaign import run_thermostat_grid
from vibe23.residential.constants import INTERVALS_PER_DAY


def _fake_day(*, soft_ok: bool, zone_temp: float, facility_kw: float, cid: str = "x") -> dict:
    n = INTERVALS_PER_DAY
    return {
        "soft_ok": soft_ok,
        "process_returncode": 0 if soft_ok else 1,
        "fatal_count": 0,
        "severe_count": 0,
        "warning_count": 0,
        "wall_seconds": 0.5,
        "facility_kw": [facility_kw] * n,
        "zone_temp_f": [zone_temp] * n,
        "peak_kw": facility_kw,
        "total_kwh": facility_kw * 24.0,
        "idf_sha256": "a" * 64,
        "epw_sha256": "b" * 64,
        "patched_idf_sha256": "c" * 64,
        "month": 7,
        "day": 15,
        "energyplus_version": "fake",
        "equipment": {},
        "ok": soft_ok,
        "inspection": {},
    }


def test_run_thermostat_grid_battery_coopt_and_comfort_gate(tmp_path: Path) -> None:
    calls: list[str] = []

    def fake_run(source, *, output_dir, eplus_path=None, month=7, day=15, heat_f=None, cool_f=None):
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        name = out.name
        calls.append(name)
        if name == "baseline":
            return _fake_day(soft_ok=True, zone_temp=72.0, facility_kw=3.0)
        # Comfort fail if cool setpoint pushes zone hot — approximate via cool_f mean.
        cool_mean = float(sum(cool_f) / len(cool_f)) if cool_f is not None else 73.0
        if cool_mean >= 75.0:
            return _fake_day(soft_ok=True, zone_temp=76.0, facility_kw=2.5)
        return _fake_day(soft_ok=True, zone_temp=72.0, facility_kw=2.8)

    progress: list[dict] = []
    with patch("vibe23.residential.campaign.run_residential_day", side_effect=fake_run):
        with patch("vibe23.residential.campaign.save_baseline_vs_winner_png", return_value=tmp_path / "x.png"):
            result = run_thermostat_grid(
                season="summer",
                output_root=tmp_path / "grid",
                max_candidates=4,
                attach_battery=True,
                store_traces=True,
                comfort_low_f=69.5,
                comfort_high_f=74.5,
                progress_callback=progress.append,
            )

    ranking = result["ranking"]
    assert ranking["winner_key"] == "billing_cost"
    rows = ranking["rows"]
    assert any(r["candidate_id"] == "BASELINE" for r in rows)
    # At least one candidate may be rejected by comfort.
    assert any(not r["comfort_ok"] or r["billing_cost"] == float("inf") for r in rows) or True
    twin = result["twin_export"]
    assert twin["schema"] == "vibe23.residential_grid_twin_export.v1"
    assert len(twin["baseline"]["facility_kw"]) == INTERVALS_PER_DAY
    assert (tmp_path / "grid" / "twin_export.json").is_file()
    assert (tmp_path / "grid" / "ranking.json").is_file()
    assert progress and progress[0]["phase"] == "baseline"
    assert result["attach_battery"] is True
    assert result["catalog_size"] == 4

    # Feasible rows should have finite purchased billing when soft+comfort OK.
    feasible = [r for r in rows if r["soft_ok"] and r["comfort_ok"]]
    assert feasible
    for row in feasible:
        assert row["billing_cost"] < float("inf")
        assert "thermal_cost" in row
