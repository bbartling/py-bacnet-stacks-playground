"""Simple YAML role mapping — no Haystack/Oxigraph."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml

ROLE_ALIASES = {
    "outside_air_temp": "oa_t",
    "outside_air_temp_f": "oa_t",
    "discharge_air_temp": "sat",
    "discharge_air_temp_f": "sat",
    "return_air_temp": "rat",
    "mixed_air_temp": "mat",
    "zone_temp": "zone_t",
    "space_temp": "zone_t",
    "supply_fan_cmd": "fan_cmd",
    "cooling_valve": "clg_valve_pct",
    "outdoor_air_damper": "oa_damper_pct",
}


def load_role_map(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {str(k): {str(r): str(c) for r, c in v.items()} for k, v in data.items() if isinstance(v, dict)}


def roles_from_columns_csv(columns_path: Path | None) -> dict[str, str]:
    """Build role→column from columns.csv point_role field."""
    if columns_path is None or not Path(columns_path).is_file():
        return {}
    import pandas as pd

    df = pd.read_csv(columns_path)
    col_key = "column" if "column" in df.columns else df.columns[0]
    role_key = next((c for c in ("point_role", "role") if c in df.columns), None)
    if role_key is None:
        return suggest_roles(pd.DataFrame(columns=df[col_key].astype(str)))
    out: dict[str, str] = {}
    for _, row in df.iterrows():
        col = str(row[col_key]).strip()
        role = str(row[role_key]).strip()
        if col and role:
            out[role] = col
    return out


def save_role_map(path: Path, mapping: dict[str, dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(mapping, sort_keys=True), encoding="utf-8")


def suggest_roles(df: pd.DataFrame) -> dict[str, str]:
    out: dict[str, str] = {}
    for col in df.columns:
        cl = col.lower()
        for key, role in ROLE_ALIASES.items():
            if key in cl:
                out[role] = col
                break
        if "space_temp" in cl and "zone_t" not in out:
            out["zone_t"] = col
        if "fan" in cl and "cmd" in cl:
            out.setdefault("fan_cmd", col)
    return out


def apply_role_map(df: pd.DataFrame, equipment_id: str, role_map: dict[str, dict[str, str]]) -> pd.DataFrame:
    eq_map = role_map.get(equipment_id, {})
    out = df.copy()
    for role, col in eq_map.items():
        if col in out.columns:
            out[role] = pd.to_numeric(out[col], errors="coerce")
    return out


def resolve_role(df: pd.DataFrame, equipment_id: str, role_map: dict, role: str) -> pd.Series | None:
    mapped = apply_role_map(df, equipment_id, role_map)
    if role in mapped.columns:
        return mapped[role]
    return None


def validate_required_roles(equipment_id: str, df: pd.DataFrame, role_map: dict, required: list[str]) -> list[str]:
    mapped = apply_role_map(df, equipment_id, role_map)
    return [r for r in required if r not in mapped.columns or mapped[r].isna().all()]
