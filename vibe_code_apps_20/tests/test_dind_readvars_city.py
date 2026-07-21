"""DinD host-path map, ReadVars (-r), root/artifacts, city provenance."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def test_artifacts_root_under_studio_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from wattlab import config as cfg

    ws = tmp_path / "data"
    ws.mkdir()
    monkeypatch.delenv("WATTLAB_ARTIFACTS", raising=False)
    monkeypatch.setenv("WATTLAB_STUDIO_WORKSPACE", str(ws))
    root = cfg.artifacts_root()
    assert root == (ws / ".artifacts").resolve()
    assert root.is_dir()


def test_host_path_for_docker_maps_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from wattlab.config import host_path_for_docker

    cont = tmp_path / "data"
    host = tmp_path / "home_ws"
    cont.mkdir()
    host.mkdir()
    nested = cont / ".artifacts" / "run1" / "file.idf"
    nested.parent.mkdir(parents=True)
    nested.write_text("x", encoding="utf-8")

    monkeypatch.setenv("WATTLAB_STUDIO_WORKSPACE", str(cont))
    monkeypatch.setenv("WATTLAB_HOST_WORKSPACE", str(host))
    mapped = host_path_for_docker(nested)
    assert mapped == (host / ".artifacts" / "run1" / "file.idf").resolve()


def test_host_path_for_docker_noop_without_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from wattlab.config import host_path_for_docker

    monkeypatch.delenv("WATTLAB_HOST_WORKSPACE", raising=False)
    monkeypatch.delenv("WATTLAB_STUDIO_WORKSPACE", raising=False)
    p = tmp_path / "a.idf"
    p.write_text("x", encoding="utf-8")
    assert host_path_for_docker(p) == p.resolve()


def test_detect_root_prefers_wattlab_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from wattlab import config as cfg

    fake = tmp_path / "app"
    (fake / "examples" / "prototypes").mkdir(parents=True)
    monkeypatch.setenv("WATTLAB_ROOT", str(fake))
    assert cfg._detect_root() == fake.resolve()


def test_troy_resolves_detroit_not_madison() -> None:
    from wattlab.defaults import resolve_city, resolve_profile

    cid, meta = resolve_city("troy")
    assert cid == "detroit"
    assert meta["climate_zone"] == "5A"
    assert "Madison" not in (meta.get("label") or "")

    profile = resolve_profile(
        {"building_type": "office", "city": "troy", "floor_area_ft2": 140_000}
    )
    # Keep user city wording; catalog id is for EPW / climate only.
    assert profile["field_sources"]["city"]["value"] == "troy"
    assert profile["climate_catalog_id"] == "detroit"
    assert profile["climate_city"] == "troy"
    note = profile["field_sources"]["city"].get("note") or ""
    assert "detroit" in note.lower()
    assert "madison" not in (profile.get("climate_city") or "").lower()


def test_unknown_city_keeps_label_not_madison() -> None:
    from wattlab.defaults import resolve_city, resolve_profile

    cid, meta = resolve_city("Springfield_IL_Custom")
    assert cid == "springfield_il_custom"
    assert meta.get("user_supplied") is True
    assert "Madison" not in (meta.get("label") or "")
    assert "conceptual" in (meta.get("epw_note") or "").lower()

    profile = resolve_profile({"building_type": "office", "city": "Springfield_IL_Custom"})
    assert profile["field_sources"]["city"]["value"] == "Springfield_IL_Custom"
    assert profile["field_sources"]["city"]["source"] == "user"


def test_run_energyplus_passes_readvars_and_host_mounts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from wattlab.energyplus import docker as dmod

    data = tmp_path / "data"
    host = tmp_path / "host"
    data.mkdir()
    host.mkdir()
    monkeypatch.setenv("WATTLAB_STUDIO_WORKSPACE", str(data))
    monkeypatch.setenv("WATTLAB_HOST_WORKSPACE", str(host))
    monkeypatch.delenv("ENERGYPLUS_DOCKER_USER", raising=False)

    idf = data / "baseline.idf"
    epw = data / "weather.epw"
    out = data / "out"
    idf.write_text("Building,\n;", encoding="utf-8")
    epw.write_text("EPW", encoding="utf-8")
    out.mkdir()

    captured: list[list[str]] = []

    def fake_run(args, **kwargs):  # noqa: ANN003, ANN201
        captured.append(list(args))
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(dmod, "docker_bin", lambda: "docker")
    monkeypatch.setattr(dmod, "ensure_image", lambda build=False: "energyplus-mcp-dev")
    with patch("wattlab.energyplus.docker.subprocess.run", side_effect=fake_run):
        dmod.run_energyplus(idf, epw, out, readvars=True)

    assert captured, "docker run was not invoked"
    args = captured[0]
    assert "-r" in args
    assert "--user" in args
    assert "1000:1000" in args
    host_ws = str(host.resolve()).replace("\\", "/")
    vol_flags = [args[i + 1] for i, a in enumerate(args) if a == "-v"]
    assert vol_flags
    joined = " ".join(v.replace("\\", "/") for v in vol_flags)
    assert "out__stage_in" in joined
    assert "/out/_stage_in" not in joined
    for v in vol_flags:
        assert host_ws in v.replace("\\", "/"), (v, host_ws)
    # Out dir must be world-writable for E+ uid 1000
    assert (out.stat().st_mode & 0o777) == 0o777 or (out.stat().st_mode & 0o222)


def test_ensure_ep_writable_chmod(tmp_path: Path) -> None:
    from wattlab.energyplus.docker import ensure_ep_writable

    p = tmp_path / "sim"
    ensure_ep_writable(p)
    assert p.is_dir()
    mode = p.stat().st_mode & 0o777
    assert mode == 0o777 or (mode & 0o002)  # world-writable bit


def test_align_idf_to_epw_partial(tmp_path: Path) -> None:
    from wattlab.energyplus.mcp import align_idf_to_epw

    idf = tmp_path / "b.idf"
    idf.write_text(
        "RunPeriod,\n  Annual,\n  1,\n  1,\n  2026,\n  12,\n  31,\n  2026,\n  Yes;\n",
        encoding="utf-8",
    )
    epw = tmp_path / "partial.epw"
    lines = [
        "LOCATION,Test,MI,USA,AMY,0,42.5,-83.1,-5.0,200.0",
        "DESIGN CONDITIONS,0",
        "TYPICAL/EXTREME PERIODS,0",
        "GROUND TEMPERATURES,0",
        "HOLIDAYS/DAYLIGHT SAVINGS,No,0,0,0",
        "COMMENTS 1,",
        "COMMENTS 2,",
        "DATA PERIODS,1,1,Data,Monday, 3/16, 7/16",
        "2026,3,16,1,0," + ",".join(["0"] * 30),
        "2026,7,16,24,0," + ",".join(["0"] * 30),
    ]
    epw.write_text("\n".join(lines) + "\n", encoding="utf-8")
    out = tmp_path / "aligned.idf"
    meta = align_idf_to_epw(idf, epw, out_idf=out)
    assert meta.get("applied") is True
    text = out.read_text(encoding="utf-8")
    assert "3," in text  # begin month
    assert "16," in text  # begin day
    assert meta["epw_begin"] == "2026-03-16"


def test_nameplate_to_capacity_factors() -> None:
    from wattlab.energyplus.sizing import nameplate_to_capacity_factors

    inv = {
        "systems": [
            {
                "system": "VAV SYS 1",
                "load_type": "Cooling",
                "user_design_capacity_w": 351685.0,  # ~100 ton
            }
        ],
        "components": [],
        "tables": {},
    }
    factors, meta = nameplate_to_capacity_factors(inv, cooling_tons=200.0)
    assert "cooling_plant" in factors
    assert abs(factors["cooling_plant"] - 2.0) < 0.05
    assert meta.get("cooling_factor")


def test_nameplate_area_scale_liberty_style() -> None:
    """140k ft² + 200 t → ~14.3 t effective on ~10k prototype (≈0.14× factor)."""
    from wattlab.config import PROTOTYPE_AREA_FT2_NOMINAL
    from wattlab.energyplus.sizing import nameplate_to_capacity_factors

    inv = {
        "systems": [
            {
                "system": "VAV SYS 1",
                "load_type": "Cooling",
                "user_design_capacity_w": 351685.0,  # ~100 ton autosized
            }
        ],
        "components": [],
        "tables": {},
    }
    scale = 140_000.0 / PROTOTYPE_AREA_FT2_NOMINAL
    factors, meta = nameplate_to_capacity_factors(
        inv, cooling_tons=200.0, prototype_area_scale=scale
    )
    # 14.3 t effective on ~100 t autosize → factor ~0.14 < 0.25 → refused
    assert meta.get("nameplate_area_scaled") is True
    assert abs(meta["cooling_tons_effective"] - (200.0 / scale)) < 0.01
    assert abs(meta["cooling_tons_effective"] - 14.26) < 0.5
    assert factors == {}
    assert meta.get("hard_size_refused") is True
    # Use a smaller autosize so scaled nameplate stays in band:
    inv_small = {
        "systems": [
            {
                "system": "VAV SYS 1",
                "load_type": "Cooling",
                "user_design_capacity_w": 35168.5,  # ~10 ton
            }
        ],
        "components": [],
        "tables": {},
    }
    factors2, meta2 = nameplate_to_capacity_factors(
        inv_small, cooling_tons=200.0, prototype_area_scale=scale
    )
    assert meta2.get("nameplate_area_scaled") is True
    assert abs(meta2["cooling_tons_effective"] - 14.26) < 0.5
    assert "cooling_plant" in factors2
    assert abs(factors2["cooling_plant"] - 1.426) < 0.1
    assert meta2.get("hard_size_refused") is False


def test_nameplate_hard_size_refused_extreme() -> None:
    from wattlab.energyplus.sizing import nameplate_to_capacity_factors

    inv = {
        "systems": [
            {
                "system": "VAV SYS 1",
                "load_type": "Cooling",
                "user_design_capacity_w": 35168.5,  # ~10 ton
            }
        ],
        "components": [],
        "tables": {},
    }
    # No area scale: 200 t on 10 t → factor 20× → refuse
    factors, meta = nameplate_to_capacity_factors(inv, cooling_tons=200.0)
    assert factors == {}
    assert meta.get("hard_size_refused") is True
    assert meta.get("refused_factors")


def test_peak_demand_kw_from_tbl_and_savings(tmp_path: Path) -> None:
    from wattlab.energyplus.results import (
        parse_eplustbl_csv,
        peak_demand_kw_from_eplusout_csv,
        savings_by_measure,
    )

    tbl = tmp_path / "eplustbl.csv"
    tbl.write_text(
        "\n".join(
            [
                "Report,Annual Building Utility Performance Summary",
                ",Total Site Energy,100.0,50.0",
                ",Total Building Area,927.2",
                ",Total End Uses,80.0,20.0",
                ",Electricity:Facility,80.0",
                "Report,Demand End Use Components Summary",
                ",Total End Uses,125000.0",
                ",Electricity:Facility,125000.0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    parsed = parse_eplustbl_csv(tbl)
    assert parsed.get("peak_demand_kw") == 125.0

    csv_path = tmp_path / "eplusout.csv"
    csv_path.write_text(
        "Date/Time,Electricity:Facility [J](Hourly)\n"
        "01/01  01:00:00,360000000\n"
        "01/01  02:00:00,720000000\n",
        encoding="utf-8",
    )
    assert peak_demand_kw_from_eplusout_csv(csv_path) == 200.0

    rows = savings_by_measure(
        [
            {
                "measure_id": None,
                "annual": {
                    "electricity_kwh_year": 1000.0,
                    "peak_demand_kw": 125.0,
                    "utility_cost_usd_year": 120.0,
                },
            },
            {
                "measure_id": "led",
                "annual": {
                    "electricity_kwh_year": 900.0,
                    "peak_demand_kw": 110.0,
                    "utility_cost_usd_year": 108.0,
                },
            },
        ]
    )
    assert rows[0]["peak_demand_kw"] == 125.0
    assert rows[1]["vs_baseline"]["peak_demand_kw_delta"] == 15.0



def test_run_energyplus_can_disable_readvars(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from wattlab.energyplus import docker as dmod

    idf = tmp_path / "a.idf"
    epw = tmp_path / "b.epw"
    out = tmp_path / "out"
    idf.write_text("x", encoding="utf-8")
    epw.write_text("y", encoding="utf-8")
    out.mkdir()
    captured: list[list[str]] = []

    def fake_run(args, **kwargs):  # noqa: ANN003, ANN201
        captured.append(list(args))
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(dmod, "docker_bin", lambda: "docker")
    monkeypatch.setattr(dmod, "ensure_image", lambda build=False: "energyplus-mcp-dev")
    with patch("wattlab.energyplus.docker.subprocess.run", side_effect=fake_run):
        dmod.run_energyplus(idf, epw, out, readvars=False)

    assert "-r" not in captured[0]


def test_epw_data_period_chicago_full_year() -> None:
    from wattlab.config import DEFAULT_MADISON_EPW
    from wattlab.weather.epw import epw_data_period

    if not DEFAULT_MADISON_EPW.is_file():
        pytest.skip("bundled EPW missing")
    span = epw_data_period(DEFAULT_MADISON_EPW)
    assert span is not None
    assert span["full_calendar_year"] is True


def test_epw_data_period_partial(tmp_path: Path) -> None:
    from wattlab.weather.epw import epw_data_period

    epw = tmp_path / "partial.epw"
    lines = [
        "LOCATION,Test,MI,USA,AMY,0,42.5,-83.1,-5.0,200.0",
        "DESIGN CONDITIONS,0",
        "TYPICAL/EXTREME PERIODS,0",
        "GROUND TEMPERATURES,0",
        "HOLIDAYS/DAYLIGHT SAVINGS,No,0,0,0",
        "COMMENTS 1,",
        "COMMENTS 2,",
        "DATA PERIODS,1,1,Data,Monday, 3/16, 7/16",
        "2026,3,16,1,0," + ",".join(["0"] * 30),
        "2026,7,16,24,0," + ",".join(["0"] * 30),
    ]
    epw.write_text("\n".join(lines) + "\n", encoding="utf-8")
    span = epw_data_period(epw)
    assert span is not None
    assert span["full_calendar_year"] is False
    assert span["begin"] == "2026-03-16"
    assert span["end"] == "2026-07-16"
    assert span.get("ok") is True
    assert span.get("end_clipped_from_partial_day") is False


def test_epw_data_period_clips_trailing_partial_day(tmp_path: Path) -> None:
    """BUG-W2b: last row hour 10 must not set RunPeriod end to that calendar day."""
    from wattlab.weather.epw import epw_data_period

    pad = ",".join(["0"] * 30)
    epw = tmp_path / "partial_hour.epw"
    lines = [
        "LOCATION,Test,MI,USA,AMY,0,42.5,-83.1,-5.0,200.0",
        "DESIGN CONDITIONS,0",
        "TYPICAL/EXTREME PERIODS,0",
        "GROUND TEMPERATURES,0",
        "HOLIDAYS/DAYLIGHT SAVINGS,No,0,0,0",
        "COMMENTS 1,",
        "COMMENTS 2,",
        "DATA PERIODS,1,1,Data,Monday, 7/15, 7/17",
        f"2026,7,15,1,0,{pad}",
        f"2026,7,15,24,0,{pad}",
        f"2026,7,16,1,0,{pad}",
        f"2026,7,16,24,0,{pad}",
        f"2026,7,17,1,0,{pad}",
        f"2026,7,17,10,0,{pad}",
    ]
    epw.write_text("\n".join(lines) + "\n", encoding="utf-8")
    span = epw_data_period(epw)
    assert span is not None
    assert span["begin"] == "2026-07-15"
    assert span["end"] == "2026-07-16"
    assert span["last_row_hour"] == 10
    assert span["end_clipped_from_partial_day"] is True
    assert span.get("ok") is True


def test_build_eui_index_bills_peers_model() -> None:
    from wattlab.studio.eui_compare import build_eui_index

    # Liberty-style screening numbers from bensbench calibrate session
    idx = build_eui_index(
        bill_eui_kbtu_ft2=71.6,
        property_type="office",
        model_eui_kbtu_ft2=23.21,
        prototype_area_scale=14.028,
        target_floor_area_ft2=140_000,
    )
    assert idx["bill_eui_kbtu_ft2"] == 71.6
    assert idx["peer_p50"] > 0
    assert idx["model_eui_kbtu_ft2"] == 23.2
    series = {r["series"] for r in idx["rows"]}
    assert "Bills (site)" in series
    assert "Peer p50 (typical)" in series
    assert "Model (prototype EUI)" in series
    # Bills above typical peer (session: 71.6 vs ~52.9)
    bill_row = next(r for r in idx["rows"] if r["series"] == "Bills (site)")
    assert bill_row["band"] in {"above_p80", "within_band", "below_p20"}
