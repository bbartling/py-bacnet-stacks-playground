"""DOCX FDD / data-model reports for browser download (python-docx)."""

from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from app.column_map_json import COOKBOOK_TO_HAYSTACK_POINT
from app.data_model_tree import BuildingDataModelTree, build_data_model_tree
from app.rules import RULES, RULES_BY_ID
from app.rules.base import RuleResult
from app.site_model import resolve_equipment_type


def _docx():
    try:
        from docx import Document  # type: ignore
        from docx.shared import Inches, Pt  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "python-docx is required for DOCX reports. Install: pip install python-docx"
        ) from exc
    return Document, Inches, Pt


def _add_heading(doc, text: str, level: int = 1) -> None:
    doc.add_heading(text, level=level)


def _add_para(doc, text: str, *, bold: bool = False) -> None:
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = bold


def _add_kv_table(doc, rows: list[tuple[str, str]]) -> None:
    table = doc.add_table(rows=1, cols=2)
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    hdr[0].text = "Field"
    hdr[1].text = "Value"
    for k, v in rows:
        cells = table.add_row().cells
        cells[0].text = str(k)
        cells[1].text = str(v)


def _role_rows_for_rule(
    rule_id: str,
    equipment_id: str,
    role_map: dict,
    mapped_cols: set[str],
) -> list[tuple[str, str, str, str]]:
    rule = RULES_BY_ID.get(rule_id)
    if rule is None:
        return []
    block = role_map.get(equipment_id) or {}
    out: list[tuple[str, str, str, str]] = []
    roles = list(rule.required_roles) + list(rule.optional_roles or [])
    # de-dupe preserve order
    seen: set[str] = set()
    for role in roles:
        if role in seen:
            continue
        seen.add(role)
        hay = COOKBOOK_TO_HAYSTACK_POINT.get(role, role.replace("_", "-"))
        csv_col = ""
        if isinstance(block, dict):
            if role in block and isinstance(block[role], str):
                csv_col = block[role]
            else:
                for c, rr in block.items():
                    if str(rr).strip() == role and c not in {
                        "equipment_type",
                        "equipType",
                        "plant_group",
                        "chw_pump_equipment",
                    }:
                        csv_col = str(c)
                        break
        present = "yes" if role in mapped_cols else "no"
        req = "required" if role in rule.required_roles else "optional"
        out.append((role, hay, csv_col or "—", f"{req} / in-history={present}"))
    return out


def build_equipment_fdd_docx(
    *,
    building_id: str,
    equipment_id: str,
    equipment_type: str,
    results: list[RuleResult],
    role_map: dict,
    mapped_df: pd.DataFrame | None,
    plot_png_by_rule: dict[str, bytes] | None = None,
) -> bytes:
    """One DOCX: all 50 rules for an equipment — description, tags, mapping, plot or placeholder."""
    Document, Inches, Pt = _docx()
    doc = Document()
    _add_heading(doc, f"FDD report — {equipment_id}", 0)
    _add_para(
        doc,
        f"Building: {building_id or '—'}  ·  Type: {equipment_type}  ·  "
        f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
    )
    _add_para(
        doc,
        "Each rule lists cookbook roles, Haystack-like tags, mapped CSV columns, "
        "and a Plotly figure when available (otherwise an empty placeholder).",
    )

    by_id = {r.rule_id: r for r in results if r.equipment_id == equipment_id}
    mapped_cols = set(mapped_df.columns) if mapped_df is not None else set()
    plot_png_by_rule = plot_png_by_rule or {}

    for rule in RULES:
        res = by_id.get(rule.id)
        status = res.status if res else "NOT_RUN"
        _add_heading(doc, f"{rule.id} — {rule.title}", 1)
        _add_para(doc, rule.equation or "")
        _add_kv_table(
            doc,
            [
                ("Status", status),
                ("Family", rule.family),
                ("Fault hours", str(res.fault_hours if res and res.fault_hours is not None else "—")),
                ("Missing roles", ", ".join(res.missing_roles) if res and res.missing_roles else "—"),
                ("Notes", (res.notes if res else "") or "—"),
            ],
        )
        _add_para(doc, "Data model bindings", bold=True)
        table = doc.add_table(rows=1, cols=4)
        table.style = "Table Grid"
        hdr = table.rows[0].cells
        hdr[0].text = "Cookbook role"
        hdr[1].text = "Haystack-like tag"
        hdr[2].text = "CSV column"
        hdr[3].text = "Requirement"
        for row in _role_rows_for_rule(rule.id, equipment_id, role_map, mapped_cols):
            cells = table.add_row().cells
            for i, val in enumerate(row):
                cells[i].text = val
        if not rule.required_roles and not rule.optional_roles:
            cells = table.add_row().cells
            cells[0].text = "(sensor/control sweep)"
            cells[1].text = "—"
            cells[2].text = "—"
            cells[3].text = "applies to present sensors / outputs"

        png = plot_png_by_rule.get(rule.id)
        if png:
            doc.add_picture(io.BytesIO(png), width=Inches(6.0))
        else:
            _add_para(
                doc,
                "[Plot placeholder] No figure for this rule on this equipment "
                "(skipped / N/A / not run / no series). See Streamlit Plots tab.",
            )

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def build_building_data_model_docx(tree: BuildingDataModelTree) -> bytes:
    Document, _Inches, _Pt = _docx()
    doc = Document()
    _add_heading(doc, f"Data model — {tree.building_id or 'building'}", 0)
    _add_para(
        doc,
        f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}. "
        "Cookbook roles ↔ Haystack-like tags ↔ raw CSV columns.",
    )
    for eq in tree.equipment:
        _add_heading(doc, f"{eq.equipment_id} ({eq.equipment_type})", 1)
        table = doc.add_table(rows=1, cols=5)
        table.style = "Table Grid"
        hdr = table.rows[0].cells
        for i, h in enumerate(
            ["Cookbook role", "Haystack tag", "CSV column", "In history", "Required by rules"]
        ):
            hdr[i].text = h
        if not eq.bindings:
            cells = table.add_row().cells
            cells[0].text = "(no bindings)"
            for i in range(1, 5):
                cells[i].text = "—"
        for b in eq.bindings:
            cells = table.add_row().cells
            cells[0].text = b.cookbook_role
            cells[1].text = b.haystack_tag
            cells[2].text = b.csv_column or "—"
            cells[3].text = "yes" if b.present_in_history else "no"
            cells[4].text = ", ".join(b.required_by_rules[:12]) + (
                "…" if len(b.required_by_rules) > 12 else ""
            )
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def build_analytics_docx(
    *,
    building_id: str,
    motor_weekly: pd.DataFrame | None = None,
    cool_bins: pd.DataFrame | None = None,
    rcx_coverage: pd.DataFrame | None = None,
    tree: BuildingDataModelTree | None = None,
) -> bytes:
    Document, _Inches, _Pt = _docx()
    doc = Document()
    _add_heading(doc, f"Analytics report — {building_id or 'building'}", 0)
    _add_para(doc, f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    def _df_section(title: str, df: pd.DataFrame | None) -> None:
        _add_heading(doc, title, 1)
        if df is None or df.empty:
            _add_para(doc, "[Placeholder] No rows for this analytics view.")
            return
        cols = list(df.columns)[:8]
        table = doc.add_table(rows=1, cols=len(cols))
        table.style = "Table Grid"
        for i, c in enumerate(cols):
            table.rows[0].cells[i].text = str(c)
        for _, row in df.head(40).iterrows():
            cells = table.add_row().cells
            for i, c in enumerate(cols):
                cells[i].text = str(row[c])
        if len(df) > 40:
            _add_para(doc, f"… {len(df) - 40} more rows (see CSV export in app).")

    _df_section("Motor run hours (weekly)", motor_weekly)
    _df_section("Mechanical cooling OAT bins", cool_bins)
    _df_section("RCx preset coverage", rcx_coverage)
    if tree is not None:
        _add_heading(doc, "Data model summary", 1)
        _add_para(doc, f"{len(tree.equipment)} equipment nodes in mapping tree.")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def try_rule_plot_png(
    mapped_df: pd.DataFrame,
    result: RuleResult,
    *,
    required_roles: list[str] | None = None,
    units_map: dict[str, str] | None = None,
) -> bytes | None:
    """Best-effort Plotly→PNG for DOCX; returns None if kaleido unavailable."""
    try:
        from app.charts import rule_result_chart

        fig = rule_result_chart(
            mapped_df,
            result,
            required_roles=required_roles,
            units_map=units_map,
        )
        if fig is None:
            return None
        return fig.to_image(format="png", width=900, height=480, scale=1)
    except Exception:
        return None
