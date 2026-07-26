"""ECMs — file viewer for agent-owned Excel notebooks (BUG-051–056)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from wattlab.studio.workspace import reports_dir

# Preferred tab order when sheets exist in the workbook
_PREFERRED_SHEETS = (
    "Calibrated_Twin",
    "Cover",
    "Inputs",
    "ESCO_Calcs",
    "EPlus_Results",
    "Compare",
    "ROI_Capital",
)

_FORMULA_CAP = 200


def _list_notebook_files(out_dir: Path) -> list[Path]:
    if not out_dir.is_dir():
        return []
    return sorted(out_dir.glob("*.xlsx"), key=lambda p: p.name.lower())


def _sheet_names(path: Path) -> list[str]:
    from openpyxl import load_workbook

    try:
        wb = load_workbook(path, read_only=True, data_only=False)
        names = list(wb.sheetnames)
        wb.close()
        return names
    except Exception:
        return []


def _ordered_sheets(present: list[str]) -> list[str]:
    ordered: list[str] = []
    for name in _PREFERRED_SHEETS:
        if name in present:
            ordered.append(name)
    for name in present:
        if name not in ordered:
            ordered.append(name)
    return ordered


def _preview_sheet_frame(path: Path, sheet: str, *, mode: str) -> pd.DataFrame | None:
    """Readonly Values or Formulas preview (never blank formula cells)."""
    from wattlab.notebooks.builder import preview_sheet_rows

    if mode == "values":
        formula_rows = preview_sheet_rows(path, sheet, max_rows=50, data_only=False)
        value_rows = preview_sheet_rows(path, sheet, max_rows=50, data_only=True)
        if not formula_rows:
            return None
        header = formula_rows[0]
        body: list[list[Any]] = []
        for i, frow in enumerate(formula_rows[1:]):
            vrow = value_rows[i + 1] if value_rows and i + 1 < len(value_rows) else []
            merged: list[Any] = []
            for j, cell in enumerate(frow):
                if isinstance(cell, str) and cell.startswith("="):
                    vc = vrow[j] if j < len(vrow) else None
                    merged.append(vc if vc is not None else cell)
                else:
                    merged.append(cell)
            body.append(merged)
        return pd.DataFrame(body, columns=header)

    rows = preview_sheet_rows(path, sheet, max_rows=50, data_only=False)
    if not rows:
        return None
    return pd.DataFrame(rows[1:], columns=rows[0])


def _cover_subtitle(path: Path) -> str:
    """Building · twin · mtime from Cover / sidecar when available."""
    parts: list[str] = []
    try:
        from openpyxl import load_workbook

        wb = load_workbook(path, read_only=True, data_only=False)
        if "Cover" in wb.sheetnames:
            cover = {str(r[0]).strip().lower(): r[1] for r in wb["Cover"].iter_rows(min_row=4, max_col=2, values_only=True) if r[0]}
            building = cover.get("building")
            twin = cover.get("twin run")
            if building:
                parts.append(str(building))
            if twin and str(twin) not in ("(none — E+ optional)",):
                parts.append(f"twin={twin}")
        wb.close()
    except Exception:
        pass
    man = path.parent / f"{path.stem}.notebook_manifest.json"
    if man.is_file() and not parts:
        try:
            data = json.loads(man.read_text(encoding="utf-8"))
            if data.get("building"):
                parts.append(str(data["building"]))
            if data.get("twin_run"):
                parts.append(f"twin={data['twin_run']}")
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    try:
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        parts.append(f"mtime {mtime.strftime('%Y-%m-%d %H:%MZ')}")
    except OSError:
        pass
    return " · ".join(parts) if parts else ""


def _load_formula_cells(path: Path) -> dict[str, dict[str, str]]:
    """Prefer manifest formula_cells; fall back to show_formulas."""
    man = path.parent / f"{path.stem}.notebook_manifest.json"
    if man.is_file():
        try:
            data = json.loads(man.read_text(encoding="utf-8"))
            cells = data.get("formula_cells")
            if isinstance(cells, dict) and cells:
                return {str(k): dict(v) for k, v in cells.items() if isinstance(v, dict)}
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    from wattlab.notebooks.builder import show_formulas

    try:
        dumped = show_formulas(path)
        sheets = dumped.get("sheets") or {}
        return {str(k): dict(v) for k, v in sheets.items() if isinstance(v, dict)}
    except Exception:
        return {}


def _render_formulas_used(path: Path) -> None:
    st.subheader("Formulas used")
    cells_by_sheet = _load_formula_cells(path)
    if not cells_by_sheet:
        st.caption("No formula map in manifest — download the workbook or run `wattlab notebook show-formulas`.")
        return
    total = 0
    lines: list[str] = []
    for sheet in _ordered_sheets(list(cells_by_sheet.keys())):
        mapping = cells_by_sheet.get(sheet) or {}
        if not mapping:
            continue
        lines.append(f"**{sheet}**")
        for addr in sorted(mapping.keys(), key=lambda a: (len(a), a)):
            if total >= _FORMULA_CAP:
                break
            formula = mapping[addr]
            lines.append(f"`{addr}` = `{formula}`")
            total += 1
        if total >= _FORMULA_CAP:
            break
    st.markdown("\n\n".join(lines) if lines else "_No formulas found._")
    if total >= _FORMULA_CAP:
        st.caption(f"Showing first {_FORMULA_CAP} formula cells — see download for full workbook.")
    else:
        st.caption(f"{total} formula cells.")


def render() -> None:
    st.header("ECMs — engineering notebooks")
    st.caption(
        "Agent owns the file under `reports/notebooks/`. "
        "Pick a workbook → readonly preview → formulas → download. "
        "Use **Reload from disk** (or hard-refresh the browser) after a CLI write."
    )
    st.markdown(
        "[ESCO calculators](https://github.com/bbartling/py-bacnet-stacks-playground/blob/develop/"
        "vibe_code_apps_20/vibe20_agent_spec/docs/ESCO_CALCULATORS.md) · "
        "[Retrofit cost / ROI](https://github.com/bbartling/py-bacnet-stacks-playground/blob/develop/"
        "vibe_code_apps_20/vibe20_agent_spec/docs/ESCO_RETROFIT_COST_ROI.md) · "
        "[Spreadsheet map](https://github.com/bbartling/py-bacnet-stacks-playground/blob/develop/"
        "vibe_code_apps_20/docs/ESCO_SPREADSHEET_CALCS.md)"
    )

    out_dir = reports_dir() / "notebooks"
    out_dir.mkdir(parents=True, exist_ok=True)
    files = _list_notebook_files(out_dir)

    if st.button("Reload from disk", key="ecm_notebook_reload"):
        for key in (
            "studio_notebook_path",
            "studio_notebook_manifest",
            "ecm_notebook_file",
            "ecm_notebook_preview_mode",
        ):
            st.session_state.pop(key, None)
        st.rerun()

    if not files:
        st.info(
            f"No `.xlsx` files under `{out_dir}` yet. "
            "Agent: `wattlab notebook agent-build --package … --out reports/notebooks/`."
        )
        return

    names = [p.name for p in files]
    by_name = {p.name: p for p in files}
    stored = st.session_state.get("ecm_notebook_file")
    if stored not in names:
        st.session_state["ecm_notebook_file"] = names[0]

    pick_name = st.selectbox(
        "Notebook file",
        names,
        key="ecm_notebook_file",
        help="On-disk workbooks only — catalog packages without a file do not appear.",
    )
    path = by_name[pick_name]
    st.session_state["studio_notebook_path"] = str(path)
    subtitle = _cover_subtitle(path)
    if subtitle:
        st.caption(subtitle)

    mode = st.radio(
        "Preview",
        options=["values", "formulas"],
        format_func=lambda k: "Values" if k == "values" else "Formulas",
        horizontal=True,
        key="ecm_notebook_preview_mode",
    )

    present = _sheet_names(path)
    sheets = _ordered_sheets(present)
    if not sheets:
        st.warning("Workbook has no sheets (or could not be opened).")
    else:
        tabs = st.tabs(sheets)
        for tab, sheet in zip(tabs, sheets):
            with tab:
                df = _preview_sheet_frame(path, sheet, mode=mode)
                if df is None or df.empty:
                    st.caption(f"Sheet `{sheet}` empty or unreadable.")
                else:
                    # Arrow-safe: stringify mixed formula/number columns
                    safe = df.copy()
                    safe.columns = [str(c) if c is not None else "" for c in safe.columns]
                    st.dataframe(safe.astype(str), width="stretch", hide_index=True)

    _render_formulas_used(path)

    st.download_button(
        "Download .xlsx",
        data=path.read_bytes(),
        file_name=path.name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="ecm_dl_notebook_xlsx",
        type="primary",
    )
    man = path.parent / f"{path.stem}.notebook_manifest.json"
    if man.is_file():
        st.download_button(
            "Download manifest (agents)",
            data=man.read_bytes(),
            file_name=man.name,
            mime="application/json",
            key="ecm_dl_notebook_manifest",
        )
