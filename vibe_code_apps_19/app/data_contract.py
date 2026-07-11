"""Building / package data-contract audits — surface warnings, never invent data."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from app.data_loader import _read_columns_map


def _parse_utc(value: Any) -> pd.Timestamp | None:
    if value is None or value == "":
        return None
    try:
        ts = pd.to_datetime(value, utc=True)
    except Exception:
        return None
    if pd.isna(ts):
        return None
    return pd.Timestamp(ts)


def load_quality_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return raw if isinstance(raw, dict) else None


def trusted_start_from_quality(quality: dict[str, Any] | None) -> pd.Timestamp | None:
    if not quality:
        return None
    for key in (
        "trusted_start_utc",
        "trusted_data_start_utc",
        "trusted_data_start",
        "trusted_start",
        "data_trusted_from",
    ):
        if key in quality:
            return _parse_utc(quality.get(key))
    nested = quality.get("quality") if isinstance(quality.get("quality"), dict) else None
    if nested:
        return trusted_start_from_quality(nested)
    return None


def audit_columns_vs_history(
    equipment_id: str,
    df: pd.DataFrame,
    columns_path: Path | None,
) -> tuple[list[str], dict[str, str]]:
    """Intersect columns.csv with history columns; warn on metadata-only points.

    Returns (warnings, col→role map limited to columns that exist in ``df``).
    """
    warnings: list[str] = []
    if not columns_path or not Path(columns_path).is_file():
        return warnings, {}
    full_map = _read_columns_map(Path(columns_path))
    hist_cols = {str(c) for c in df.columns}
    present = {c: r for c, r in full_map.items() if c in hist_cols}
    missing = sorted(set(full_map) - hist_cols)
    if missing:
        preview = ", ".join(missing[:8])
        extra = f" (+{len(missing) - 8} more)" if len(missing) > 8 else ""
        warnings.append(
            f"{equipment_id}: columns.csv lists {len(missing)} point(s) absent from "
            f"history_wide.csv — ignored for mapping: {preview}{extra}"
        )
    return warnings, present


def audit_quality_window(
    equipment_id: str,
    df: pd.DataFrame,
    quality: dict[str, Any] | None,
    *,
    parent_quality: dict[str, Any] | None = None,
    parent_id: str | None = None,
) -> list[str]:
    """Warn when quality trusted-start would zero out rows. Does not filter the frame."""
    warnings: list[str] = []
    q = quality
    source = "own quality.json"
    if q is None and parent_quality is not None:
        q = parent_quality
        source = f"parent AHU quality.json ({parent_id or 'parent'})"
    if q is None:
        return warnings
    start = trusted_start_from_quality(q)
    if start is None:
        return warnings
    if not isinstance(df.index, pd.DatetimeIndex) or df.empty:
        return warnings
    data_end = df.index.max()
    data_start = df.index.min()
    trusted = df.index[df.index >= start]
    if len(trusted) == 0:
        warnings.append(
            f"{equipment_id}: {source} trusted_start={start} is after data end "
            f"{data_end} — would yield 0 trusted rows. Keeping full history "
            f"[{data_start} → {data_end}]; do not invent or backdate trusted data."
        )
    elif start > data_start:
        warnings.append(
            f"{equipment_id}: {source} trusted_start={start} drops "
            f"{int((df.index < start).sum())} early row(s) before trusted window "
            f"(data still loaded unfiltered; filter only if caller opts in)."
        )
    return warnings


def load_vav_to_ahu_map(building_root: Path) -> dict[str, str]:
    """Return VAV id → AHU id from optional ``vav_to_ahu_simple.csv``."""
    path = Path(building_root) / "vav_to_ahu_simple.csv"
    if not path.is_file():
        return {}
    try:
        topo = pd.read_csv(path)
    except Exception:
        return {}
    cols = {c.lower(): c for c in topo.columns}
    vav_col = cols.get("vav") or cols.get("vav_id") or cols.get("terminal") or cols.get("equipment_id")
    ahu_col = cols.get("ahu") or cols.get("ahu_id") or cols.get("parent") or cols.get("serves")
    if not vav_col or not ahu_col:
        # two-column file without headers
        if topo.shape[1] >= 2:
            vav_col, ahu_col = topo.columns[0], topo.columns[1]
        else:
            return {}
    out: dict[str, str] = {}
    for _, row in topo.iterrows():
        v = str(row[vav_col]).strip()
        a = str(row[ahu_col]).strip()
        if v and a and v.lower() not in {"vav", "vav_id", "nan"}:
            out[v] = a
    return out


def infer_parent_ahu_from_path(eq_folder: Path, building_root: Path) -> str | None:
    """Best-effort parent AHU from folder layout (e.g. VAV under an AHU tree)."""
    try:
        rel = eq_folder.resolve().relative_to(Path(building_root).resolve())
    except Exception:
        return None
    parts = list(rel.parts)
    for part in parts:
        up = part.upper()
        if up.startswith("AHU") and up != eq_folder.name.upper():
            return part
    return None


def audit_building_topology(
    building_root: Path,
    equipment: list[dict[str, Any]],
) -> tuple[list[str], dict[str, str]]:
    """Warn on VAV↔topology mismatches. Returns (warnings, vav→ahu map used)."""
    warnings: list[str] = []
    topo = load_vav_to_ahu_map(building_root)
    vav_ids = []
    for eq in equipment:
        eid = str(eq.get("equipment_id") or "")
        folder = Path(eq.get("folder") or ".")
        # VAV folder heuristic: under a VAV/ parent or name starts with VAV
        parts = [p.upper() for p in folder.parts]
        if "VAV" in parts or eid.upper().startswith("VAV"):
            vav_ids.append(eid)

    missing_topo = sorted(v for v in vav_ids if v not in topo)
    if missing_topo:
        preview = ", ".join(missing_topo[:8])
        extra = f" (+{len(missing_topo) - 8} more)" if len(missing_topo) > 8 else ""
        warnings.append(
            f"Topology: {len(missing_topo)} VAV folder(s) not in vav_to_ahu_simple.csv "
            f"— parent-AHU fallback via path/quality only: {preview}{extra}"
        )

    orphan_topo = sorted(v for v in topo if v not in set(vav_ids))
    if orphan_topo:
        preview = ", ".join(orphan_topo[:8])
        extra = f" (+{len(orphan_topo) - 8} more)" if len(orphan_topo) > 8 else ""
        warnings.append(
            f"Topology: {len(orphan_topo)} vav_to_ahu_simple.csv id(s) have no VAV folder: "
            f"{preview}{extra}"
        )
    return warnings, topo


def audit_equipment_package(
    *,
    equipment_id: str,
    df: pd.DataFrame,
    eq_folder: Path,
    building_root: Path,
    topo: dict[str, str],
) -> list[str]:
    """Full per-equipment contract warnings (columns + quality)."""
    warnings: list[str] = []
    cols_path = eq_folder / "columns.csv"
    col_warn, present_map = audit_columns_vs_history(equipment_id, df, cols_path if cols_path.is_file() else None)
    warnings.extend(col_warn)
    if present_map:
        df.attrs["columns_roles_present"] = present_map
        df.attrs["columns_roles_ignored"] = sorted(
            set(_read_columns_map(cols_path)) - set(present_map)
        ) if cols_path.is_file() else []

    own_q = load_quality_json(eq_folder / "quality.json")
    parent_id = topo.get(equipment_id) or infer_parent_ahu_from_path(eq_folder, building_root)
    parent_q = None
    if parent_id:
        # Prefer sibling AHU folder under building root
        candidate = Path(building_root) / parent_id / "quality.json"
        if not candidate.is_file():
            # AHU may live at building_root/AHU_n
            for p in Path(building_root).rglob("quality.json"):
                if p.parent.name == parent_id:
                    candidate = p
                    break
        parent_q = load_quality_json(candidate)
    warnings.extend(
        audit_quality_window(
            equipment_id,
            df,
            own_q,
            parent_quality=parent_q if own_q is None else None,
            parent_id=parent_id,
        )
    )
    if own_q is None and parent_q is not None:
        warnings.append(
            f"{equipment_id}: no quality.json — using parent AHU '{parent_id}' quality for trust checks only"
        )
    return warnings


def audit_package_dir(
    building_root: Path,
    frames: dict[str, pd.DataFrame],
    equipment: list[dict[str, Any]],
) -> list[str]:
    """Run building-level + per-equip audits; mutate frame attrs for present roles."""
    warnings, topo = audit_building_topology(building_root, equipment)
    by_id = {str(e["equipment_id"]): e for e in equipment}
    for eid, df in frames.items():
        eq = by_id.get(eid)
        if not eq:
            continue
        folder = Path(eq["folder"])
        warnings.extend(
            audit_equipment_package(
                equipment_id=eid,
                df=df,
                eq_folder=folder,
                building_root=building_root,
                topo=topo,
            )
        )
    # Cap spam in UI — keep all in report, return full list (caller may truncate display)
    return warnings
