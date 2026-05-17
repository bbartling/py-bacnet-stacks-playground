"""
Scheduled open-fdd evaluation on DynamoDB telemetry (container Lambda).

Install: open-fdd[engine] — see https://github.com/bbartling/open-fdd
Rules: rules/*.yaml (bounds 65–80 °F, flatline, rate per hour/minute)
"""

from __future__ import annotations

import json
import os
import time
from decimal import Decimal
from pathlib import Path

import boto3
import pandas as pd
from boto3.dynamodb.conditions import Key
from open_fdd.engine.runner import RuleRunner

TABLE_NAME = os.environ.get("TABLE_NAME", "vibe12-telemetry")
DEVICE_ID = os.environ.get("DEVICE_ID", "bosspi-ds18b20")
LOOKBACK_HOURS = float(os.environ.get("LOOKBACK_HOURS", "6"))
RULES_DIR = Path(__file__).resolve().parent / "rules"

_table = boto3.resource("dynamodb").Table(TABLE_NAME)

# open-fdd column_map: Brick logical name → DataFrame column
COLUMN_MAP = {"Zone_Temperature_Sensor": "degF"}

FLAG_LABELS = {
    "temp_out_of_bounds_flag": "Out of bounds (65–80 °F)",
    "temp_flatline_flag": "Flatline (stuck sensor)",
    "temp_rate_per_hour_flag": "Rate high (> 15 °F/hr)",
    "temp_rate_per_minute_flag": "Rate high (> 2 °F/min)",
}


def _fetch_readings(hours: float) -> list[dict]:
    cutoff_ms = int((time.time() - hours * 3600) * 1000)
    resp = _table.query(
        KeyConditionExpression=Key("device_id").eq(DEVICE_ID) & Key("ts_ms").gte(cutoff_ms),
        ScanIndexForward=True,
        Limit=2000,
    )
    return resp.get("Items", [])


def _to_dataframe(items: list[dict]) -> pd.DataFrame:
    if not items:
        return pd.DataFrame(columns=["timestamp", "degF", "degC"])

    rows = []
    for it in items:
        ts_ms = int(it["ts_ms"])
        if ts_ms <= 0 or "degF" not in it or "degC" not in it:
            continue
        rows.append(
            {
                "timestamp": pd.to_datetime(ts_ms, unit="ms", utc=True),
                "degF": float(it["degF"]),
                "degC": float(it["degC"]),
                "ts_ms": ts_ms,
            }
        )
    df = pd.DataFrame(rows).sort_values("timestamp")
    return df.reset_index(drop=True)


def _primary_status(active_flags: list[str]) -> str:
    if not active_flags:
        return "NORMAL"
    # Strip _flag suffix for display
    return active_flags[0].replace("_flag", "").upper()


def lambda_handler(event, context):
    items = _fetch_readings(LOOKBACK_HOURS)
    df = _to_dataframe(items)

    if df.empty:
        summary = {
            "fdd_status": "MISSING_DATA",
            "active_flags": [],
            "sample_count": 0,
            "lookback_hours": LOOKBACK_HOURS,
        }
    else:
        eval_log: list[str] = [
            f"Loaded {len(df)} samples over {LOOKBACK_HOURS}h",
            f"degF range {df['degF'].min():.2f} .. {df['degF'].max():.2f}",
        ]
        try:
            runner = RuleRunner(rules_path=RULES_DIR)
            result = runner.run(
                df,
                timestamp_col="timestamp",
                column_map=COLUMN_MAP,
                input_validation="warn",
                skip_missing_columns=True,
            )
        except Exception as exc:
            eval_log.append(f"ERROR RuleRunner: {exc}")
            raise

        flag_cols = [c for c in result.columns if c.endswith("_flag")]
        eval_log.append(f"Flag columns: {', '.join(flag_cols) or '(none)'}")
        active_flags: list[str] = []
        flag_counts: dict[str, int] = {}
        for col in flag_cols:
            count = int(result[col].fillna(0).sum())
            flag_counts[col] = count
            eval_log.append(f"  {col}: {count} flagged samples (rolling_window=6 in YAML)")
            if count > 0:
                active_flags.append(col)

        summary = {
            "fdd_status": _primary_status(active_flags),
            "active_flags": active_flags,
            "flag_counts": flag_counts,
            "sample_count": len(df),
            "lookback_hours": LOOKBACK_HOURS,
            "latest_degF": float(df["degF"].iloc[-1]),
            "latest_degC": float(df["degC"].iloc[-1]),
            "ts_ms": [int(v) for v in result["ts_ms"].tolist()],
            "flag_series": {
                col: result[col].fillna(0).astype(int).tolist() for col in flag_cols
            },
            "flag_labels": FLAG_LABELS,
            "eval_log": eval_log,
            "evaluated_at": int(time.time()),
        }

    _table.put_item(
        Item={
            "device_id": DEVICE_ID,
            "ts_ms": 0,
            "record_type": "fdd_status",
            "fdd_status": summary["fdd_status"],
            "active_flags": ",".join(summary.get("active_flags", [])),
            "summary_json": json.dumps(summary),
            "sample_count": summary.get("sample_count", 0),
            "updated_at": int(time.time()),
            "expires_at": int(time.time()) + 30 * 86400,
        }
    )

    return summary
