"""IDF preflight + ExampleFiles/DataSets compatibility (local EnergyPlus gated)."""
from __future__ import annotations

from pathlib import Path

import pytest

from vibe23.studio.idf_geometry import parse_idf_geometry
from vibe23.studio.idf_inspect import inspect_idf
from vibe23.studio.idf_preflight import preflight_idf

DATA = Path(__file__).resolve().parent / "data"
EPLUS_ROOT = Path(r"C:\EnergyPlusV26-1-0")
HAS_EPLUS = EPLUS_ROOT.is_dir()

EXAMPLE_FILES = [
    "Minimal.idf",
    "1ZoneUncontrolled3SurfaceZone.idf",
    "1ZoneUncontrolledResLayers.idf",
    "1ZoneUncontrolled.idf",
    "1ZoneEvapCooler.idf",
    "ZoneWSHP_wDOAS.idf",
    "RefBldgSmallOfficeNew2004_Chicago.idf",
]

DATASET_FILES = [
    "Boilers.idf",
    "PerfCurves.idf",
    "Schedules.idf",
    "RooftopPackagedHeatPump.idf",
]


def test_preflight_minimal_no_surfaces() -> None:
    pf = preflight_idf(DATA / "minimal_no_surfaces.idf")
    assert pf.can_visualize is False
    assert any("BuildingSurface:Detailed" in b for b in pf.blockers)
    inspect_idf(DATA / "minimal_no_surfaces.idf")  # must not raise
    geom = parse_idf_geometry((DATA / "minimal_no_surfaces.idf").read_text(encoding="utf-8"))
    assert len(geom.surfaces) == 0


def test_preflight_surfaces_missing_setpoints() -> None:
    pf = preflight_idf(DATA / "one_zone_surfaces_no_setpoints.idf")
    assert pf.can_visualize is True
    assert pf.can_simulate is False
    assert pf.has_heat_setpoint_schedule is False
    assert pf.has_cool_setpoint_schedule is False
    assert any("HEAT SETPOINT" in b for b in pf.blockers)
    assert any("COOL SETPOINT" in b for b in pf.blockers)
    assert any("Electricity:Facility" in b for b in pf.blockers)
    assert pf.declared_timestep == 6
    assert any("Timestep=6" in w for w in pf.warnings)


def test_preflight_residential_ok_snippet() -> None:
    pf = preflight_idf(DATA / "residential_ok_snippet.idf")
    assert pf.can_visualize is True
    assert pf.can_simulate is True
    assert pf.has_heat_setpoint_schedule is True
    assert pf.has_cool_setpoint_schedule is True
    assert pf.has_facility_meter_timestep is True
    assert pf.has_zone_temp_timestep is True
    assert pf.declared_timestep == 12
    assert pf.n_zones >= 2
    assert any("multi-zone" in w for w in pf.warnings)
    assert pf.blockers == []


def test_preflight_repo_model_idf() -> None:
    from vibe23.residential.model import MODEL_IDF

    pf = preflight_idf(MODEL_IDF)
    assert pf.can_visualize is True
    assert pf.can_simulate is True
    assert pf.declared_timestep == 12


@pytest.mark.skipif(not HAS_EPLUS, reason="EnergyPlus 26.1 not installed")
@pytest.mark.parametrize("name", EXAMPLE_FILES)
def test_examplefiles_inspect_and_geometry_do_not_raise(name: str) -> None:
    path = EPLUS_ROOT / "ExampleFiles" / name
    assert path.is_file(), path
    text = path.read_text(encoding="utf-8", errors="replace")
    inspect_idf(text, source_name=name)
    parse_idf_geometry(text)
    preflight_idf(text, source_name=name)


@pytest.mark.skipif(not HAS_EPLUS, reason="EnergyPlus 26.1 not installed")
@pytest.mark.parametrize("name", DATASET_FILES)
def test_datasets_inspect_and_geometry_do_not_raise(name: str) -> None:
    path = EPLUS_ROOT / "DataSets" / name
    assert path.is_file(), path
    text = path.read_text(encoding="utf-8", errors="replace")
    inspect_idf(text, source_name=name)
    parse_idf_geometry(text)
    pf = preflight_idf(text, source_name=name)
    assert pf.can_visualize is False
    assert pf.can_simulate is False


@pytest.mark.skipif(not HAS_EPLUS, reason="EnergyPlus 26.1 not installed")
def test_minimal_idf_cannot_visualize() -> None:
    pf = preflight_idf(EPLUS_ROOT / "ExampleFiles" / "Minimal.idf")
    assert pf.can_visualize is False
    assert any("BuildingSurface:Detailed" in b for b in pf.blockers)


@pytest.mark.skipif(not HAS_EPLUS, reason="EnergyPlus 26.1 not installed")
def test_evap_cooler_missing_setpoint_schedules() -> None:
    pf = preflight_idf(EPLUS_ROOT / "ExampleFiles" / "1ZoneEvapCooler.idf")
    assert pf.has_heat_setpoint_schedule is False
    assert pf.has_cool_setpoint_schedule is False
    assert pf.can_simulate is False
    assert any("HEAT SETPOINT" in b or "COOL SETPOINT" in b for b in pf.blockers)


@pytest.mark.skipif(not HAS_EPLUS, reason="EnergyPlus 26.1 not installed")
def test_ref_bldg_small_office_multi_zone() -> None:
    pf = preflight_idf(EPLUS_ROOT / "ExampleFiles" / "RefBldgSmallOfficeNew2004_Chicago.idf")
    assert pf.n_zones > 1
    assert any("multi-zone" in w for w in pf.warnings)
