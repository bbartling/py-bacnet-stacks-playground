#!/usr/bin/env python
"""CLI smoke for vibe22 (no Streamlit; no live EnergyPlus required for status)."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP))


def _minimal_site(tmp: Path) -> Path:
    (tmp / "utilities").mkdir(parents=True)
    (tmp / "reports" / "eplus_gym").mkdir(parents=True)
    (tmp / "eplus" / "models").mkdir(parents=True)
    (tmp / "utilities" / "campus.json").write_text(
        json.dumps(
            {
                "campus_id": "smoke_campus",
                "label": "Smoke Campus",
                "lat": 43.0,
                "lon": -89.0,
                "buildings": [{"building_id": "b1", "floor_area_ft2": 50000}],
                "meters": [],
            }
        ),
        encoding="utf-8",
    )
    (tmp / "eplus" / "models" / "demo_champion.idf").write_text(
        "Version,24.2;\nBuilding,Demo,0,Suburbs,0.04,0.4,FullExterior,25,6;\n",
        encoding="utf-8",
    )
    (tmp / "reports" / "site_ui_bundle_v1.json").write_text(
        json.dumps(
            {
                "schema_version": "site_ui_bundle_v1",
                "campus_json": "utilities/campus.json",
                "default_model_id": "CHAMPION",
                "current_model_id": "CHAMPION",
                "dsm_champion": "CHAMPION",
                "idf_pin": "demo_champion.idf",
                "model_catalog": [
                    {
                        "id": "CHAMPION",
                        "label": "Demo champion",
                        "family": "W2A_PHYSICAL_DSM",
                        "idf_pin": "demo_champion.idf",
                        "champion": True,
                    }
                ],
                "honesty": {"bas": "BAS_INTERVAL_METER"},
            }
        ),
        encoding="utf-8",
    )
    return tmp


def main() -> int:
    from eplus_gym_app.optimize_tomorrow import approve_recommendation, list_studies
    from eplus_gym_app.site_config import load_site_dsm_config, save_site_dsm_config
    from eplus_native.six_zone_htg_stage import ACTION_KEYS

    assert ACTION_KEYS == ("1F_A", "1F_B", "1F_C", "1F_D", "2F_A", "2F_B")
    with tempfile.TemporaryDirectory(prefix="vibe22_cli_smoke_") as td:
        site = _minimal_site(Path(td))
        os.environ["SITE_ROOT"] = str(site)
        cfg = load_site_dsm_config(site)
        save_site_dsm_config(site, cfg)
        assert list_studies(site) == []
        # Approve helper only writes approved_recommendation.json
        root = site / "reports" / "eplus_gym" / "optimization" / "smoke_study"
        root.mkdir(parents=True)
        (root / "recommendation.json").write_text(
            json.dumps({"recommended": {"feasible": True}}), encoding="utf-8"
        )
        out = approve_recommendation(root)
        assert out.is_file()
        assert "streamlit" not in out.read_text(encoding="utf-8").lower()
        # CLI status
        code = os.system(
            f'"{sys.executable}" "{_APP / "scripts" / "vibe22.py"}" status --site-root "{site}"'
        )
        if code != 0:
            print("STATUS_FAIL", code)
            return 2
    print("SMOKE_CLI_OK")
    print("streamlit=REMOVED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
