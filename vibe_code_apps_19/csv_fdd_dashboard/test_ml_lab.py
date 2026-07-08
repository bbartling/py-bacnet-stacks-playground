"""Unit tests for the ML lab helpers (no server, no network)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import ml_lab


def test_safe_module_name_sanitizes():
    assert ml_lab.safe_module_name("My Cool Rule.py") == "my_cool_rule.py"
    assert ml_lab.safe_module_name("../../etc/passwd") == "passwd.py"  # dir traversal stripped
    assert ml_lab.safe_module_name("123start.py") == "ml_123start.py"
    assert ml_lab.safe_module_name("") == "uploaded_rule.py"


def test_save_upload_rejects_non_python(tmp_path, monkeypatch):
    monkeypatch.setattr(ml_lab, "PLUGIN_DIR", tmp_path)
    with pytest.raises(ValueError):
        ml_lab.save_upload("bad.py", b"this is (not python")


def test_save_upload_rejects_binary(tmp_path, monkeypatch):
    monkeypatch.setattr(ml_lab, "PLUGIN_DIR", tmp_path)
    with pytest.raises(ValueError):
        ml_lab.save_upload("x.py", b"\xff\xfe\x00\x01")


def test_save_and_read_plugin(tmp_path, monkeypatch):
    monkeypatch.setattr(ml_lab, "PLUGIN_DIR", tmp_path)
    info = ml_lab.save_upload("demo rule.py", b"x = 1\n")
    assert info["name"] == "demo_rule.py"
    assert ml_lab.read_plugin("demo_rule.py").strip() == "x = 1"
    assert any(f["name"] == "demo_rule.py" for f in ml_lab.list_plugins())


def test_pip_validation_accepts_specs():
    assert ml_lab._validate_packages("scikit-learn pandas==2.2.1") == ["scikit-learn", "pandas==2.2.1"]
    assert ml_lab._validate_packages("uvicorn[standard]") == ["uvicorn[standard]"]


@pytest.mark.parametrize("bad", ["evil; rm -rf /", "pkg && curl x", "a|b", "$(whoami)", "../pkg"])
def test_pip_validation_rejects_injection(bad):
    with pytest.raises(ValueError):
        ml_lab._validate_packages(bad)


def test_pip_validation_caps_count():
    with pytest.raises(ValueError):
        ml_lab._validate_packages(" ".join(f"pkg{i}" for i in range(ml_lab.MAX_PIP_PACKAGES + 1)))


def test_persist_fault_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(ml_lab, "FAULT_STORE_DIR", tmp_path)
    n = 20
    ts = pd.date_range("2026-03-01", periods=n, freq="5min", tz="UTC")
    fault = pd.Series([False] * n)
    fault.iloc[3:6] = True  # 3 fault rows
    summary = ml_lab.persist_fault("AHU_9", "ML-TEST", fault, timestamps=ts, poll_seconds=300.0)

    assert summary["rows"] == n
    assert summary["fault_rows"] == 3
    assert summary["fault_hours"] == pytest.approx(3 * 300 / 3600.0)
    assert summary["verified"] is True

    stores = ml_lab.list_fault_stores()
    assert stores and stores[0]["rule_id"] == "ML-TEST"

    # Feather file exists and round-trips with a timestamp column.
    feather_path, _ = ml_lab._fault_store_paths("AHU_9", "ML-TEST")
    back = pd.read_feather(feather_path)
    assert list(back.columns) == ["timestamp", "fault_confirmed"]
    assert int(back["fault_confirmed"].sum()) == 3


def test_persist_fault_without_timestamps(tmp_path, monkeypatch):
    monkeypatch.setattr(ml_lab, "FAULT_STORE_DIR", tmp_path)
    fault = pd.Series(np.array([True, False, True]))
    summary = ml_lab.persist_fault("P1", "R1", fault)
    assert summary["fault_rows"] == 2
    assert summary["verified"] is True
