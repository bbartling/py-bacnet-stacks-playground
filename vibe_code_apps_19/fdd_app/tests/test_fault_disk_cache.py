"""Tests for disk-backed cookbook fault cache."""

import fault_disk_cache as fdc


def test_fault_disk_cache_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(fdc, "_CACHE_DIR", tmp_path / "faults")
    token = "test-token-abc"
    key = "view|AHU_1|ahu|hash"
    data = {"equipment_id": "AHU_1", "rules": [], "n_rules": 0}

    assert fdc.get(token, key) is None
    fdc.put(token, key, data)
    hit = fdc.get(token, key)
    assert hit is not None
    assert hit["equipment_id"] == "AHU_1"
    assert fdc.rule_set_version() == "1"
