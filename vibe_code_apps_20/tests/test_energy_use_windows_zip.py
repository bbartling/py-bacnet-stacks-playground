"""Regression coverage for Windows-created energy-use archives."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from wattlab.energy_use import load_energy_use_package


def test_windows_zip_separators_discover_wrapped_campus_package(tmp_path: Path):
    package = tmp_path / "campus_liberty_practice"
    package.mkdir()
    (package / "campus.json").write_text(
        json.dumps(
            {
                "campus_id": "demo",
                "label": "Demo",
                "lat": 42.0,
                "lon": -83.0,
                "buildings": [],
                "meters": [],
            }
        ),
        encoding="utf-8",
    )
    (package / "bill_column_map.json").write_text(
        json.dumps({"version": 1, "siteRef": "demo"}),
        encoding="utf-8",
    )

    archive = tmp_path / "campus.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        for path in package.iterdir():
            zf.write(path, arcname=f"campus_liberty_practice\\{path.name}")

    loaded = load_energy_use_package(archive)

    assert loaded.campus is not None
    assert loaded.campus.campus_id == "demo"
