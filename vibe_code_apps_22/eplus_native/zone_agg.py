"""Nine E+ zone → six BAS area temperature aggregation (contract v1)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import pandas as pd

_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT = _ROOT / "contracts" / "eplus_nine_to_six_zone_agg_v1.json"

WeightMode = Literal["hp_count", "floor_area"]


def load_agg_contract(path: Path | str | None = None) -> dict[str, Any]:
    p = Path(path) if path else _DEFAULT
    return json.loads(p.read_text(encoding="utf-8"))


def member_weights(contract: dict[str, Any], bas_zone: str, mode: WeightMode) -> dict[str, float]:
    agg = contract["aggregation"][bas_zone]
    members = list(agg["members"])
    src = contract["default_hp_counts"] if mode == "hp_count" else contract["default_floor_area_ft2"]
    raw = {m: float(src[m]) for m in members}
    s = sum(raw.values()) or 1.0
    return {m: v / s for m, v in raw.items()}


def aggregate_zone_temps_row(
    temps_f: dict[str, float],
    contract: dict[str, Any] | None = None,
    *,
    mode: WeightMode = "hp_count",
) -> dict[str, float]:
    cal = contract or load_agg_contract()
    out: dict[str, float] = {}
    for bas, out_col in cal["output_cols"].items():
        w = member_weights(cal, bas, mode)
        out[out_col] = float(sum(temps_f[m] * w[m] for m in w))
    return out


def aggregate_zone_temp_frame(
    df: pd.DataFrame,
    *,
    contract: dict[str, Any] | None = None,
    mode: WeightMode = "hp_count",
    eplus_zone_cols: dict[str, str] | None = None,
) -> pd.DataFrame:
    """``eplus_zone_cols`` maps E+ zone name → column in ``df`` (°F).

    Vectorized (no ``iterrows``) — annual 15-min frames are ~30k+ rows.
    """
    cal = contract or load_agg_contract()
    if eplus_zone_cols is None:
        eplus_zone_cols = {z: z for z in cal["eplus_zones_nine"]}
    out: dict[str, Any] = {}
    for bas, out_col in cal["output_cols"].items():
        w = member_weights(cal, bas, mode)
        series = None
        for member, weight in w.items():
            col = eplus_zone_cols[member]
            part = df[col].astype(float) * float(weight)
            series = part if series is None else series + part
        out[out_col] = series
    return pd.DataFrame(out, index=df.index)
