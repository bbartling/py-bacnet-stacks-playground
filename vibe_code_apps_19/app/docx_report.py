"""DOCX FDD / data-model reports for browser download (python-docx)."""

from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from app.data_model_tree import BuildingDataModelTree, build_data_model_tree
from app.rule_card import (
    PLACE_PLOT_HERE,
    RuleCard,
    build_rule_card,
    equipment_mapping_coverage,
)
from app.rules import RULES, RULES_BY_ID
from app.rules.base import RuleResult
from app.rules.cookbook_catalog import CookbookRule
from app.rules.runner import infer_equipment_kind


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


def applicable_rules_for_equipment(
    equipment_id: str,
    *,
    equipment_type: str = "",
    mapped_df: pd.DataFrame | None = None,
    role_map: dict | None = None,
) -> list[CookbookRule]:
    """Canonical cookbook rules applicable to this device's equipment kind."""
    kind = infer_equipment_kind(
        equipment_id,
        equipment_type=equipment_type,
        df=mapped_df,
        role_map=role_map,
    )
    if kind == "unknown":
        return list(RULES)
    return [r for r in RULES if kind in r.equipment_kinds]


def _add_params_table(doc, card: RuleCard) -> None:
    _add_para(doc, "Tune parameters", bold=True)
    table = doc.add_table(rows=1, cols=5)
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    for i, h in enumerate(["Key", "Label", "Value", "Unit", "Source"]):
        hdr[i].text = h
    if not card.param_rows:
        cells = table.add_row().cells
        cells[0].text = "(no tune params)"
        for i in range(1, 5):
            cells[i].text = "—"
        return
    for pr in card.param_rows:
        cells = table.add_row().cells
        cells[0].text = pr.key
        cells[1].text = pr.label
        cells[2].text = f"{pr.value:g}"
        cells[3].text = pr.unit
        cells[4].text = pr.source


def _add_mapping_table(doc, card: RuleCard) -> None:
    _add_para(doc, "Required vs mapped points", bold=True)
    table = doc.add_table(rows=1, cols=5)
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    for i, h in enumerate(
        ["Cookbook role", "Haystack-like tag", "CSV column", "Requirement", "In history"]
    ):
        hdr[i].text = h
    if not card.mapping_rows:
        cells = table.add_row().cells
        cells[0].text = "(sensor/control sweep — applies to present sensors / outputs)"
        for i in range(1, 5):
            cells[i].text = "—"
        return
    for m in card.mapping_rows:
        cells = table.add_row().cells
        cells[0].text = m.role
        cells[1].text = m.haystack_tag
        cells[2].text = m.csv_column
        cells[3].text = m.requirement
        cells[4].text = "yes" if m.in_history else "MISSING"


def _append_rule_card_section(
    doc,
    card: RuleCard,
    *,
    plot_png: bytes | None,
    Inches,
) -> None:
    _add_heading(doc, f"{card.rule_id} — {card.title} · {card.status}", 1)
    if card.equation:
        _add_para(doc, card.equation)
    fh = "—" if card.fault_hours is None else f"{card.fault_hours:.2f}"
    _add_kv_table(
        doc,
        [
            ("Status", card.status),
            ("Family", card.family),
            ("Fault hours", fh),
            (
                "Missing roles",
                ", ".join(card.missing_roles) if card.missing_roles else "—",
            ),
            ("Notes", card.notes or "—"),
            (
                "Required mapping",
                (
                    f"{card.required_roles_present}/{card.required_roles_total}"
                    if card.required_roles_total
                    else "n/a (sweep)"
                ),
            ),
        ],
    )
    _add_params_table(doc, card)
    _add_mapping_table(doc, card)
    _add_para(doc, "Plot", bold=True)
    if plot_png:
        doc.add_picture(io.BytesIO(plot_png), width=Inches(6.0))
    else:
        _add_para(doc, PLACE_PLOT_HERE)


def build_equipment_fdd_docx(
    *,
    building_id: str,
    equipment_id: str,
    equipment_type: str,
    results: list[RuleResult],
    role_map: dict,
    mapped_df: pd.DataFrame | None,
    plot_png_by_rule: dict[str, bytes] | None = None,
    params: dict[str, Any] | None = None,
    rules: list[CookbookRule] | None = None,
    motor_weekly: pd.DataFrame | None = None,
    cool_bins: pd.DataFrame | None = None,
) -> bytes:
    """DOCX mirror of Plots rule cards: params, mapping, PLACE PLOT HERE stubs."""
    Document, Inches, _Pt = _docx()
    doc = Document()
    applicable = rules or applicable_rules_for_equipment(
        equipment_id,
        equipment_type=equipment_type,
        mapped_df=mapped_df,
        role_map=role_map,
    )
    present, total, cov_pct = equipment_mapping_coverage(
        applicable, equipment_id, role_map, mapped_df
    )
    _add_heading(doc, f"FDD validation report — {equipment_id}", 0)
    _add_kv_table(
        doc,
        [
            ("Building", building_id or "—"),
            ("Equipment", equipment_id),
            ("Type", equipment_type or "—"),
            (
                "Mapping coverage",
                f"{cov_pct:.0f}% required roles present ({present}/{total})",
            ),
            (
                "Generated",
                datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            ),
            ("Rules in report", str(len(applicable))),
        ],
    )
    _add_para(
        doc,
        "Each section mirrors a Plots validation card: equation, status, tune params, "
        "required vs mapped points, and a plot stub for paste-in figures.",
    )

    by_id = {r.rule_id: r for r in results if r.equipment_id == equipment_id}
    plot_png_by_rule = plot_png_by_rule or {}

    for rule in applicable:
        card = build_rule_card(
            equipment_id=equipment_id,
            rule=rule,
            result=by_id.get(rule.id),
            role_map=role_map,
            mapped_df=mapped_df,
            params=params,
        )
        _append_rule_card_section(
            doc,
            card,
            plot_png=plot_png_by_rule.get(rule.id),
            Inches=Inches,
        )

    # Optional short analytics appendix (tables only)
    if motor_weekly is not None or cool_bins is not None:
        _add_heading(doc, "Analytics appendix", 1)
        if motor_weekly is not None and not motor_weekly.empty:
            _add_para(doc, "Motor weekly (summary)", bold=True)
            cols = list(motor_weekly.columns)[:6]
            table = doc.add_table(rows=1, cols=len(cols))
            table.style = "Table Grid"
            for i, c in enumerate(cols):
                table.rows[0].cells[i].text = str(c)
            for _, row in motor_weekly.head(20).iterrows():
                cells = table.add_row().cells
                for i, c in enumerate(cols):
                    cells[i].text = str(row[c])
        if cool_bins is not None and not cool_bins.empty:
            _add_para(doc, "Mechanical cooling OAT bins (summary)", bold=True)
            cols = list(cool_bins.columns)[:6]
            table = doc.add_table(rows=1, cols=len(cols))
            table.style = "Table Grid"
            for i, c in enumerate(cols):
                table.rows[0].cells[i].text = str(c)
            for _, row in cool_bins.head(20).iterrows():
                cells = table.add_row().cells
                for i, c in enumerate(cols):
                    cells[i].text = str(row[c])

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
