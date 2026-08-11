"""Every bundle JSON must parse and must not contain pandas repr artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from app.bundle_io import dumps_json_safe
from app.wattlab_dump import BUNDLE_SCHEMA, LEGACY_BUNDLE_SCHEMA, build_manifest, fdd_findings_table
from open_fdd.rules.evidence import assert_no_pandas_repr


def test_dumps_json_safe_rejects_pandas_repr():
    idx = pd.date_range("2024-01-01", periods=80, freq="5min", tz="UTC")
    series = pd.Series(range(80), index=idx, name="discharge-air-temp")
    text = dumps_json_safe({"metric": series})
    parsed = json.loads(text)
    assert "count" in parsed["metric"]
    assert_no_pandas_repr(text)
    assert "..." not in text


def test_manifest_schema_has_legacy_alias(tmp_path: Path):
    payload = build_manifest({}, tmp_path)
    assert payload["schema_version"] == BUNDLE_SCHEMA
    assert payload["legacy_schema_version"] == LEGACY_BUNDLE_SCHEMA
    text = json.dumps(payload)
    assert_no_pandas_repr(text)


def test_findings_metrics_are_json_safe():
    from app.rules.base import RuleResult

    idx = pd.date_range("2024-01-01", periods=3, freq="5min", tz="UTC")
    result = RuleResult(
        rule_id="DEMO",
        equipment_id="AHU_1",
        status="PASS",
        applicable=True,
        fault_hours=0.0,
        fault_pct=0.0,
        fault_sample_count=0,
        sample_count=3,
        metrics={"series": pd.Series([1.0, 2.0, 3.0], index=idx)},
    )
    table = fdd_findings_table([result])
    records = table.to_dict(orient="records")
    blob = dumps_json_safe(records)
    json.loads(blob)
    assert_no_pandas_repr(blob)
