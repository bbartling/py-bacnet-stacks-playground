"""Docker integration smoke for OpenFDD WattLab (requires Docker + energyplus-mcp-dev)."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def docker_ready():
    from ep_docker import docker_info_ok, image_present

    if not docker_info_ok():
        pytest.skip("Docker not available")
    if not image_present():
        pytest.skip("energyplus-mcp-dev image missing")
    return True


def test_ep_version_in_container(docker_ready) -> None:
    from ep_mcp_client import get_server_status_via_docker

    status = get_server_status_via_docker()
    assert status["energyplus_ok"]
    assert "26.1" in status["energyplus_version"]


def test_sample_sim_and_result_record_fields(docker_ready, tmp_path: Path) -> None:
    from config import DEFAULT_MADISON_EPW, DEFAULT_PROTOTYPE_IDF
    from ep_mcp_client import simulate
    from results_parse import annual_from_output_dir, build_result_record

    out = tmp_path / "sim"
    # Use shortened path: full 5Zone annual is fine for CI gate
    meta = simulate(DEFAULT_PROTOTYPE_IDF, DEFAULT_MADISON_EPW, out)
    assert meta["ok"], meta
    annual = annual_from_output_dir(out)
    assert annual.get("ok")
    assert annual.get("electricity_kwh_year") is not None
    assert annual.get("site_eui_kbtu_ft2_year") is not None
    rr = build_result_record(
        run_id="smoke",
        measure_id=None,
        idf_path=DEFAULT_PROTOTYPE_IDF,
        annual=annual,
    )
    for key in ("run_id", "measure_id", "input_hash", "status", "quality_flags", "annual"):
        assert key in rr
    assert rr["status"] == "COMPLETE"
    assert rr["input_hash"]
