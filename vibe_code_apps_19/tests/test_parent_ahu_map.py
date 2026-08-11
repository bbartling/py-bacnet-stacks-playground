"""Real Building 100 topology header must not map AHU ids onto tower numbers."""

from __future__ import annotations

from pathlib import Path

from app.data_contract import audit_building_topology, load_vav_to_ahu_map


B100_HEADER = "parent_ahu,tower,floor,vav_id,vav_key,history_column,data_file"


def test_parent_ahu_header_not_positional_fallback(tmp_path: Path):
    root = tmp_path / "B100"
    root.mkdir()
    (root / "vav_to_ahu_simple.csv").write_text(
        f"{B100_HEADER}\n"
        "AHU_1,100,1,VAV_7,VAV-7,zone_t,VAV_7/history_wide.csv\n"
        "AHU_2,100,2,VAV_8,VAV-8,zone_t,VAV_8/history_wide.csv\n",
        encoding="utf-8",
    )
    topo = load_vav_to_ahu_map(root)
    assert topo == {"VAV_7": "AHU_1", "VAV_8": "AHU_2"}
    assert "AHU_1" not in topo
    assert "100" not in topo.values()


def test_observed_vav_rows_are_not_stale_equipment(tmp_path: Path):
    root = tmp_path / "B1"
    (root / "AHU_1").mkdir(parents=True)
    (root / "VAV" / "VAV_A").mkdir(parents=True)
    (root / "vav_to_ahu_simple.csv").write_text(
        "parent_ahu,tower,floor,vav_id,vav_key,history_column,data_file\n"
        "AHU_1,100,1,VAV_A,VAV-A,zone_t,VAV_A/history_wide.csv\n"
        "AHU_1,100,1,VAV_GHOST,VAV-GHOST,zone_t,missing.csv\n",
        encoding="utf-8",
    )
    equipment = [
        {"equipment_id": "AHU_1", "folder": root / "AHU_1"},
        {"equipment_id": "VAV_A", "folder": root / "VAV" / "VAV_A"},
    ]
    _w, topo, health, issues = audit_building_topology(root, equipment)
    assert topo["VAV_A"] == "AHU_1"
    assert health.observed_map_count == 1
    assert health.stale_map_id_count == 0
    codes = {i.code for i in issues}
    assert "topology.observed_map_ids" in codes
    assert "topology.stale_map_ids" not in codes
