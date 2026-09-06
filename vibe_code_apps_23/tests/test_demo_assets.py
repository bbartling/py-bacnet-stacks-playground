"""Packaged demo assets + thermostat catalog shape."""
from __future__ import annotations

from vibe23.residential.experiment import default_thermostat_candidates
from vibe23.residential.model import DEFAULT_EPW, MODEL_IDF, ensure_demo_assets
from vibe23.residential.thermostat import center_search_values


def test_ensure_demo_assets_resolves_package_files() -> None:
    paths = ensure_demo_assets(download_if_missing=False)
    assert paths["idf"].is_file()
    assert paths["epw"].is_file()
    assert MODEL_IDF.is_file()
    assert DEFAULT_EPW.is_file()
    assert paths["idf"].resolve() == MODEL_IDF.resolve()
    assert paths["epw"].resolve() == DEFAULT_EPW.resolve()


def test_full_catalog_is_13_by_13() -> None:
    centers = center_search_values()
    assert len(centers) == 13
    assert centers[0] == 69.0
    assert centers[-1] == 75.0
    cands = default_thermostat_candidates(season="summer")
    assert len(cands) == 169
