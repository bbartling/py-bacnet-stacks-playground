"""Build / validate / summarize ECM engineering notebooks (openpyxl)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from wattlab.notebooks.packages import (
    INPUT_NAMED_RANGES,
    REQUIRED_SHEETS,
    NotebookPackage,
    get_notebook_package,
    list_notebook_packages,
)

ESCO_DOCS_URL = (
    "https://github.com/bbartling/py-bacnet-stacks-playground/blob/develop/"
    "vibe_code_apps_20/docs/ESCO_SPREADSHEET_CALCS.md"
)
YELLOW = "FFFF99"
HEADER_FILL = "1F4E79"
HEADER_FONT = "FFFFFF"


def _style_header(ws, row: int = 1) -> None:
    from openpyxl.styles import Font, PatternFill

    fill = PatternFill("solid", fgColor=HEADER_FILL)
    font = Font(color=HEADER_FONT, bold=True)
    for cell in ws[row]:
        cell.fill = fill
        cell.font = font


def _yellow(cell) -> None:
    from openpyxl.styles import PatternFill

    cell.fill = PatternFill("solid", fgColor=YELLOW)


def _define_name(wb, name: str, sheet: str, cell: str) -> None:
    from openpyxl.workbook.defined_name import DefinedName

    # Remove prior definition if rebuilding
    if name in wb.defined_names:
        del wb.defined_names[name]
    wb.defined_names.add(DefinedName(name, attr_text=f"'{sheet}'!{cell}"))


def default_inputs_from_profile(profile: dict[str, Any] | None = None) -> dict[str, Any]:
    from wattlab.studio.proxies import resolve_proxy_inputs

    profile = profile or {}
    try:
        resolved = resolve_proxy_inputs(profile)
    except Exception:
        resolved = {
            "area_ft2": float(profile.get("conditioned_floor_area_ft2") or profile.get("floor_area_ft2") or 50000),
            "cooling_tons": profile.get("cooling_tons"),
            "fan_hp": profile.get("fan_hp") or profile.get("supply_fan_hp"),
        }
    rates = profile.get("utility") if isinstance(profile.get("utility"), dict) else {}
    return {
        "area_ft2": float(resolved.get("area_ft2") or 50000),
        "cooling_tons": resolved.get("cooling_tons"),
        "fan_hp": resolved.get("fan_hp"),
        "elec_rate": float(rates.get("elec_usd_per_kwh") or 0.12),
        "gas_rate": float(rates.get("gas_usd_per_therm") or 0.80),
        "discount": 0.05,
        "escalation": 0.02,
        "life_years": 15,
        "usd_per_ft2": 3.0,
        "coverage": 1.0,
        "building": str(profile.get("building_id") or profile.get("name") or "BUILDING"),
        "property_type": str(profile.get("building_type") or profile.get("property_type") or "office"),
    }


def _ep_by_measure(report: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for s in (report or {}).get("savings_by_measure") or []:
        mid = s.get("measure_id")
        vs = s.get("vs_previous") or s.get("vs_baseline") or {}
        if mid:
            out[str(mid)] = vs
    return out


def build_notebook_workbook(
    package: NotebookPackage | str,
    *,
    profile: dict[str, Any] | None = None,
    report: dict[str, Any] | None = None,
    input_overrides: dict[str, Any] | None = None,
    proxies: dict[str, dict[str, Any]] | None = None,
    costs: dict[str, float] | None = None,
    gate: dict[str, Any] | None = None,
) -> Any:
    """Return an openpyxl Workbook for one package notebook."""
    from openpyxl import Workbook
    from openpyxl.styles import Font

    from wattlab.crosscheck import crosscheck_measure
    from wattlab.finance import capital_plan, measure_economics
    from wattlab.studio.ecm_roi import implementation_cost_usd
    from wattlab.studio.proxies import DEFAULT_MEASURE_COSTS, estimate_proxy_savings

    pkg = get_notebook_package(package) if isinstance(package, str) else package
    inputs = default_inputs_from_profile(profile)
    if input_overrides:
        inputs.update({k: v for k, v in input_overrides.items() if v is not None})

    measure_ids = list(pkg.measure_ids)
    if proxies is None:
        proxies = estimate_proxy_savings(profile or {"floor_area_ft2": inputs["area_ft2"]}, measure_ids)
    ep_by = _ep_by_measure(report)

    area = float(inputs["area_ft2"])
    cov = float(inputs["coverage"])
    usd_ft2 = float(inputs["usd_per_ft2"])
    if costs is None:
        costs = {}
        for mid in measure_ids:
            costs[mid] = implementation_cost_usd(
                floor_area_ft2=area,
                usd_per_ft2=usd_ft2,
                coverage_fraction=cov,
                fixed_usd=None,
            )
            if costs[mid] <= 0:
                costs[mid] = float(DEFAULT_MEASURE_COSTS.get(mid, 10000.0))

    econ_rows = []
    compare_rows = []
    for mid in measure_ids:
        p = proxies.get(mid) or {}
        ep = ep_by.get(mid) or {}
        esco_kwh = float(p.get("savings_kwh") or 0.0)
        esco_therms = float(p.get("savings_therms") or 0.0)
        ep_kwh = ep.get("kwh_saved")
        ep_therms = ep.get("therms_saved")
        xc = crosscheck_measure(
            measure_id=mid,
            ep_savings_kwh=None if ep_kwh is None else float(ep_kwh),
            proxy_savings_kwh=esco_kwh,
            ep_savings_therms=None if ep_therms is None else float(ep_therms),
            proxy_savings_therms=esco_therms,
        )
        # Prefer E+ for capital when present
        kwh_for_econ = float(ep_kwh) if ep_kwh is not None else esco_kwh
        therms_for_econ = float(ep_therms) if ep_therms is not None else esco_therms
        econ_rows.append(
            measure_economics(
                measure_id=mid,
                implementation_cost_usd=float(costs.get(mid) or 0),
                kwh_saved=kwh_for_econ,
                therms_saved=therms_for_econ,
                elec_rate_usd_per_kwh=float(inputs["elec_rate"]),
                gas_rate_usd_per_therm=float(inputs["gas_rate"]),
                discount_rate=float(inputs["discount"]),
                escalation_rate=float(inputs["escalation"]),
                measure_life_years=int(inputs["life_years"]),
            )
        )
        compare_rows.append(
            {
                "measure_id": mid,
                "esco_kwh": esco_kwh,
                "ep_kwh": ep_kwh,
                "esco_therms": esco_therms,
                "ep_therms": ep_therms,
                "verdict": xc.get("verdict_canonical") or xc.get("verdict"),
                "agreement_ratio": xc.get("agreement_ratio"),
                "calculators": ",".join(p.get("calculators") or []) if isinstance(p.get("calculators"), list) else "",
            }
        )

    plan = capital_plan(econ_rows)
    if gate is None:
        try:
            from wattlab.benchmarks.guardrails import gate_capital_plan

            gate = gate_capital_plan(
                plan,
                property_type=str(inputs.get("property_type") or "office"),
                floor_area_ft2=area,
                site_eui_kbtu_ft2=None,
            )
        except Exception:
            gate = {"verdict": "UNKNOWN", "checks": [], "investigate_count": 0}

    wb = Workbook()

    # --- Cover ---
    cover = wb.active
    cover.title = "Cover"
    cover["A1"] = "WattLab Engineering Notebook"
    cover["A1"].font = Font(bold=True, size=16)
    cover["A2"] = "ECM package screening (ESCO bin-method vs EnergyPlus)"
    rows = [
        ("Building", inputs.get("building")),
        ("Package id", pkg.id),
        ("Package", pkg.label),
        ("Honesty", pkg.honesty),
        ("Generated (UTC)", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")),
        ("Catalog package", pkg.catalog_package),
        ("n_measures", len(measure_ids)),
        ("Guardrail verdict", gate.get("verdict")),
        ("ESCO docs", ESCO_DOCS_URL),
        (
            "Note",
            "Yellow Inputs drive rate-linked Excel formulas (annual $, payback, NPV, cost B=H). "
            "ESCO kWh/therms are Python screening proxies baked at build — not bin-method Excel "
            "(see Docs + ESCO_SPREADSHEET_CALCS.md). Scaffold template is not loaded at build.",
        ),
    ]
    for i, (k, v) in enumerate(rows, start=4):
        cover[f"A{i}"] = k
        cover[f"B{i}"] = v
    cover.column_dimensions["A"].width = 22
    cover.column_dimensions["B"].width = 72

    # --- Inputs (yellow + named ranges) ---
    inp = wb.create_sheet("Inputs")
    inp.append(["parameter", "value", "unit", "notes"])
    _style_header(inp)
    input_rows = [
        ("area_ft2", inputs["area_ft2"], "ft²", "Conditioned floor area", "inp_area_ft2"),
        ("cooling_tons", inputs.get("cooling_tons") or "", "tons", "Optional nameplate", "inp_cooling_tons"),
        ("fan_hp", inputs.get("fan_hp") or "", "HP", "Optional supply fan", "inp_fan_hp"),
        ("elec_rate", inputs["elec_rate"], "$/kWh", "Blended electric rate", "inp_elec_rate"),
        ("gas_rate", inputs["gas_rate"], "$/therm", "Blended gas rate", "inp_gas_rate"),
        ("discount", inputs["discount"], "fraction", "NPV discount rate", "inp_discount"),
        ("escalation", inputs["escalation"], "fraction", "Utility escalation", "inp_escalation"),
        ("life_years", inputs["life_years"], "yr", "Measure life", "inp_life_years"),
        ("usd_per_ft2", inputs["usd_per_ft2"], "$/ft²", "Fallback package cost intensity", "inp_usd_per_ft2"),
        ("coverage", inputs["coverage"], "0–1", "Fraction of floor area receiving ECMs", "inp_coverage"),
    ]
    for i, (param, val, unit, notes, named) in enumerate(input_rows, start=2):
        inp[f"A{i}"] = param
        inp[f"B{i}"] = val
        inp[f"C{i}"] = unit
        inp[f"D{i}"] = notes
        _yellow(inp[f"B{i}"])
        _define_name(wb, named, "Inputs", f"$B${i}")
    inp.column_dimensions["A"].width = 18
    inp.column_dimensions["B"].width = 14
    inp.column_dimensions["D"].width = 40

    # --- ESCO_Calcs ---
    esco = wb.create_sheet("ESCO_Calcs")
    esco.append(
        [
            "measure_id",
            "savings_kwh",
            "savings_therms",
            "calculators",
            "annual_cost_saved_formula",
            "notes",
        ]
    )
    _style_header(esco)
    for i, mid in enumerate(measure_ids, start=2):
        p = proxies.get(mid) or {}
        esco[f"A{i}"] = mid
        esco[f"B{i}"] = float(p.get("savings_kwh") or 0)
        esco[f"C{i}"] = float(p.get("savings_therms") or 0)
        calcs = p.get("calculators")
        esco[f"D{i}"] = ",".join(calcs) if isinstance(calcs, list) else ""
        # Formula references Inputs named rates
        esco[f"E{i}"] = f"=B{i}*inp_elec_rate+C{i}*inp_gas_rate"
        esco[f"F{i}"] = (
            "B/C = Python screening proxy at build (not live Excel bins). "
            "E updates when Inputs rates change."
        )
    esco.column_dimensions["A"].width = 28
    esco.column_dimensions["D"].width = 28
    esco.column_dimensions["E"].width = 28
    esco.column_dimensions["F"].width = 48

    # --- EPlus_Results ---
    ep_ws = wb.create_sheet("EPlus_Results")
    ep_ws.append(["measure_id", "kwh_saved", "therms_saved", "peak_kw_delta", "source"])
    _style_header(ep_ws)
    for i, mid in enumerate(measure_ids, start=2):
        ep = ep_by.get(mid) or {}
        ep_ws[f"A{i}"] = mid
        ep_ws[f"B{i}"] = ep.get("kwh_saved")
        ep_ws[f"C{i}"] = ep.get("therms_saved")
        ep_ws[f"D{i}"] = ep.get("peak_demand_kw_delta")
        ep_ws[f"E{i}"] = "Twin savings_by_measure" if ep else "E+ not run — ESCO only"
    ep_ws.column_dimensions["A"].width = 28
    ep_ws.column_dimensions["E"].width = 28

    # --- Compare (formulas vs ESCO / E+ sheets) ---
    cmp_ws = wb.create_sheet("Compare")
    cmp_ws.append(
        [
            "measure_id",
            "esco_kwh",
            "ep_kwh",
            "delta_kwh",
            "ratio_ep_esco",
            "esco_therms",
            "ep_therms",
            "verdict",
            "light",
        ]
    )
    _style_header(cmp_ws)
    for i, row in enumerate(compare_rows, start=2):
        cmp_ws[f"A{i}"] = row["measure_id"]
        cmp_ws[f"B{i}"] = f"=ESCO_Calcs!B{i}"
        cmp_ws[f"C{i}"] = f"=EPlus_Results!B{i}"
        cmp_ws[f"D{i}"] = f'=IF(OR(C{i}="",C{i}=0),"",C{i}-B{i})'
        cmp_ws[f"E{i}"] = f'=IF(OR(B{i}=0,C{i}=""),"",C{i}/B{i})'
        cmp_ws[f"F{i}"] = f"=ESCO_Calcs!C{i}"
        cmp_ws[f"G{i}"] = f"=EPlus_Results!C{i}"
        cmp_ws[f"H{i}"] = row["verdict"]
        has_ep = row["ep_kwh"] is not None or row["ep_therms"] is not None
        v = str(row["verdict"] or "").upper()
        if not has_ep:
            light = "YELLOW"
        elif v == "IN_LINE":
            light = "GREEN"
        elif "REASONABLE" in v or "INSUFFICIENT" in v:
            light = "YELLOW"
        else:
            light = "RED"
        cmp_ws[f"I{i}"] = light
    cmp_ws.column_dimensions["A"].width = 28

    # --- ROI_Capital ---
    roi = wb.create_sheet("ROI_Capital")
    roi.append(
        [
            "measure_id",
            "implementation_cost_usd",
            "kwh_saved",
            "therms_saved",
            "annual_cost_saved_usd",
            "simple_payback_years",
            "npv_usd",
            "cost_formula",
            "npv_usd_at_build",
        ]
    )
    _style_header(roi)
    n_meas = max(len(measure_ids), 1)
    # Closed-form NPV of escalated annuity (matches wattlab.finance.escalated_cash_flows + npv)
    npv_formula = (
        "=IF(ABS(inp_discount-inp_escalation)<1E-9,"
        "-B{i}+E{i}*inp_life_years/(1+inp_discount),"
        "-B{i}+E{i}*(1-((1+inp_escalation)/(1+inp_discount))^inp_life_years)"
        "/(inp_discount-inp_escalation))"
    )
    for i, row in enumerate(econ_rows, start=2):
        roi[f"A{i}"] = row["measure_id"]
        # H = Inputs-driven equal-split cost; B mirrors H (engineer may overwrite B with a lump sum)
        roi[f"H{i}"] = f"=inp_usd_per_ft2*inp_area_ft2*inp_coverage/{n_meas}"
        roi[f"B{i}"] = f"=H{i}"
        roi[f"C{i}"] = row["kwh_saved"]
        roi[f"D{i}"] = row["therms_saved"]
        roi[f"E{i}"] = f"=C{i}*inp_elec_rate+D{i}*inp_gas_rate"
        roi[f"F{i}"] = f'=IF(E{i}=0,"",B{i}/E{i})'
        roi[f"G{i}"] = npv_formula.format(i=i)
        _yellow(roi[f"B{i}"])  # still highlight — overwrite formula with fixed $ if needed
        # Cached build-time NPV for agents / Studio preview (not Excel-evaluated)
        roi[f"I{i}"] = row["npv_usd"]
    # Totals
    n = len(econ_rows)
    if n:
        tot = n + 2
        roi[f"A{tot}"] = "TOTAL"
        roi[f"B{tot}"] = f"=SUM(B2:B{n+1})"
        roi[f"E{tot}"] = f"=SUM(E2:E{n+1})"
        roi[f"G{tot}"] = f"=SUM(G2:G{n+1})"
        roi[f"I{tot}"] = f"=SUM(I2:I{n+1})"
        roi[f"A{tot}"].font = Font(bold=True)
    roi.column_dimensions["A"].width = 28
    roi.column_dimensions["H"].width = 36
    roi.column_dimensions["I"].width = 18

    # --- Guardrails ---
    gr = wb.create_sheet("Guardrails")
    gr.append(["check", "status", "detail"])
    _style_header(gr)
    gr["A2"] = "overall_verdict"
    gr["B2"] = gate.get("verdict")
    gr["C2"] = f"investigate_count={gate.get('investigate_count')}"
    r = 3
    for c in gate.get("checks") or []:
        gr[f"A{r}"] = c.get("check")
        gr[f"B{r}"] = c.get("status")
        gr[f"C{r}"] = c.get("detail")
        r += 1
    gr.column_dimensions["A"].width = 28
    gr.column_dimensions["C"].width = 60

    # --- Docs ---
    docs = wb.create_sheet("Docs")
    docs["A1"] = "Documentation & calculator map"
    docs["A1"].font = Font(bold=True, size=14)
    docs["A3"] = "ESCO spreadsheet calcs (human map)"
    docs["B3"] = ESCO_DOCS_URL
    docs["A4"] = "Python bin calculators"
    docs["B4"] = "wattlab/bench/esco.py · wattlab/studio/proxies.py"
    docs["A5"] = "Crosscheck"
    docs["B5"] = "wattlab/crosscheck.py (~0.5–2× = reasonable)"
    docs["A6"] = "Finance / NPV"
    docs["B6"] = (
        "ROI_Capital G = live Excel closed-form NPV from Inputs rates + E; "
        "I = Python NPV at build (wattlab/finance.py) for agents without Excel calc"
    )
    docs["A7"] = "Catalog package"
    docs["B7"] = pkg.catalog_package
    docs["A8"] = "Measure ids"
    docs["B8"] = ", ".join(measure_ids)
    docs["A9"] = "Template file"
    docs["B9"] = (
        "templates/ecm_package_v1.xlsx is a write-template scaffold only — "
        "builds always generate Workbook() in builder.py (BUG-033 honesty)"
    )
    docs["A10"] = "Agent CLI"
    docs["B10"] = (
        f"wattlab notebook build --package {pkg.id} --out reports/notebooks/ "
        f"| wattlab notebook prefill --xlsx … --elec-rate 0.22  (in-place Inputs)"
    )
    docs["A11"] = "E+ Compare"
    docs["B11"] = (
        "YELLOW light when Twin report lacks savings_by_measure — "
        "pick an ECM-capable run (validate warns); easy-button needs Docker sock"
    )
    docs["A12"] = "ESCO kWh/therms honesty"
    docs["B12"] = (
        "Baked at build via wattlab.studio.proxies / bench/esco.py — "
        "not live Excel bin blocks. Human map: docs/ESCO_SPREADSHEET_CALCS.md"
    )
    docs["A13"] = "Agent refresh"
    docs["B13"] = (
        "wattlab notebook prefill (Inputs) | refresh-caches (npv_usd_at_build) | "
        "show-formulas --sheet ROI_Capital"
    )
    docs.column_dimensions["A"].width = 28
    docs.column_dimensions["B"].width = 80

    wb.properties.title = f"WattLab notebook · {pkg.id}"
    wb.properties.creator = "WattLab"
    return wb


def save_workbook(wb: Any, path: Path | str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


# Map CLI / profile override keys → Inputs parameter names (column A)
_INPUT_PARAM_ALIASES: dict[str, str] = {
    "area_ft2": "area_ft2",
    "conditioned_floor_area_ft2": "area_ft2",
    "floor_area_ft2": "area_ft2",
    "cooling_tons": "cooling_tons",
    "fan_hp": "fan_hp",
    "supply_fan_hp": "fan_hp",
    "elec_rate": "elec_rate",
    "elec_usd_per_kwh": "elec_rate",
    "gas_rate": "gas_rate",
    "gas_usd_per_therm": "gas_rate",
    "discount": "discount",
    "escalation": "escalation",
    "life_years": "life_years",
    "usd_per_ft2": "usd_per_ft2",
    "coverage": "coverage",
}


def read_notebook_inputs(path: Path | str) -> dict[str, Any]:
    """Read Inputs!A/B yellow parameters from an existing workbook."""
    from openpyxl import load_workbook

    path = Path(path)
    wb = load_workbook(path, data_only=False)
    if "Inputs" not in wb.sheetnames:
        return {}
    out: dict[str, Any] = {}
    for row in wb["Inputs"].iter_rows(min_row=2, max_col=2, values_only=True):
        if row[0]:
            out[str(row[0])] = row[1]
    return out


def prefill_notebook_inputs(
    path: Path | str,
    *,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Patch yellow Inputs cells in-place — keeps EPlus_Results / ESCO / formulas (BUG-030).

    Only keys present in ``overrides`` are written. Does **not** rebuild the workbook
    or refill unspecified Inputs from defaults.
    """
    from openpyxl import load_workbook
    from openpyxl.styles import PatternFill

    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)

    patch: dict[str, Any] = {}
    for k, v in (overrides or {}).items():
        if v is None:
            continue
        param = _INPUT_PARAM_ALIASES.get(str(k), str(k))
        patch[param] = v

    if not patch:
        return {"path": str(path), "updated": [], "inputs": read_notebook_inputs(path)}

    wb = load_workbook(path, data_only=False)
    if "Inputs" not in wb.sheetnames:
        raise ValueError(f"Inputs sheet missing in {path}")
    ws = wb["Inputs"]
    row_by: dict[str, int] = {}
    for r in range(2, (ws.max_row or 2) + 1):
        key = ws.cell(r, 1).value
        if key:
            row_by[str(key)] = r
    updated: list[str] = []
    yellow = PatternFill("solid", fgColor=YELLOW)
    for param, val in patch.items():
        if param not in row_by:
            continue
        cell = ws.cell(row_by[param], 2)
        cell.value = val
        cell.fill = yellow
        updated.append(param)
    wb.save(path)
    return {"path": str(path), "updated": updated, "inputs": read_notebook_inputs(path)}


def collect_formula_cells(
    path: Path | str,
    *,
    sheets: tuple[str, ...] = ("ESCO_Calcs", "Compare", "ROI_Capital"),
    max_cells: int = 500,
) -> dict[str, dict[str, str]]:
    """Map sheet → {A1: formula} for agent formula UX (BUG-044)."""
    from openpyxl import load_workbook
    from openpyxl.utils import get_column_letter

    path = Path(path)
    wb = load_workbook(path, data_only=False)
    out: dict[str, dict[str, str]] = {}
    n = 0
    for sheet in sheets:
        if sheet not in wb.sheetnames:
            continue
        ws = wb[sheet]
        cells: dict[str, str] = {}
        for row in ws.iter_rows(min_row=1, max_row=ws.max_row or 1, max_col=ws.max_column or 1):
            for cell in row:
                val = cell.value
                if isinstance(val, str) and val.startswith("="):
                    addr = f"{get_column_letter(cell.column)}{cell.row}"
                    cells[addr] = val
                    n += 1
                    if n >= max_cells:
                        out[sheet] = cells
                        return out
        if cells:
            out[sheet] = cells
    return out


def show_formulas(
    path: Path | str,
    *,
    sheet: str | None = None,
) -> dict[str, Any]:
    """CLI-friendly formula dump for one sheet or all formula sheets."""
    path = Path(path)
    sheets = (sheet,) if sheet else ("ESCO_Calcs", "Compare", "ROI_Capital", "Inputs")
    cells = collect_formula_cells(path, sheets=tuple(s for s in sheets if s))
    return {"path": str(path.resolve()), "sheets": cells}


def refresh_notebook_caches(path: Path | str) -> dict[str, Any]:
    """Recompute Python cache columns without wiping formulas (BUG-044).

    Updates ``ROI_Capital!I`` (npv_usd_at_build) from current Inputs rates +
    ROI C/D savings and cost (H formula evaluated in Python from Inputs).
    Does not rewrite Inputs, Compare formulas, ESCO B/C, or EPlus_Results.
    """
    from openpyxl import load_workbook

    from wattlab.finance import measure_economics

    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    wb = load_workbook(path, data_only=False)
    if "Inputs" not in wb.sheetnames or "ROI_Capital" not in wb.sheetnames:
        raise ValueError("Inputs and ROI_Capital sheets required")

    inputs = {}
    for row in wb["Inputs"].iter_rows(min_row=2, max_col=2, values_only=True):
        if row[0]:
            inputs[str(row[0])] = row[1]

    def _f(key: str, default: float) -> float:
        try:
            v = inputs.get(key)
            return float(v) if v is not None and v != "" else float(default)
        except (TypeError, ValueError):
            return float(default)

    area = _f("area_ft2", 50000)
    usd = _f("usd_per_ft2", 3.0)
    cov = _f("coverage", 1.0)
    elec = _f("elec_rate", 0.12)
    gas = _f("gas_rate", 0.80)
    disc = _f("discount", 0.05)
    esc = _f("escalation", 0.02)
    life = int(_f("life_years", 15))

    roi = wb["ROI_Capital"]
    # Count measure rows (stop at TOTAL / blank)
    measure_rows: list[int] = []
    for r in range(2, (roi.max_row or 2) + 1):
        mid = roi.cell(r, 1).value
        if mid is None or str(mid).strip() == "" or str(mid).upper() == "TOTAL":
            break
        measure_rows.append(r)
    n_meas = max(len(measure_rows), 1)
    package_cost = usd * area * cov / n_meas

    updated = 0
    for r in measure_rows:
        mid = str(roi.cell(r, 1).value)
        # Cost: if B is formula, use package_cost; else numeric override
        bval = roi.cell(r, 2).value
        if isinstance(bval, str) and bval.startswith("="):
            cost = package_cost
        else:
            try:
                cost = float(bval) if bval is not None else package_cost
            except (TypeError, ValueError):
                cost = package_cost
        try:
            kwh = float(roi.cell(r, 3).value or 0)
        except (TypeError, ValueError):
            kwh = 0.0
        try:
            therms = float(roi.cell(r, 4).value or 0)
        except (TypeError, ValueError):
            therms = 0.0
        econ = measure_economics(
            measure_id=mid,
            implementation_cost_usd=cost,
            kwh_saved=kwh,
            therms_saved=therms,
            elec_rate_usd_per_kwh=elec,
            gas_rate_usd_per_therm=gas,
            discount_rate=disc,
            escalation_rate=esc,
            measure_life_years=life,
        )
        # Column I = npv_usd_at_build (header row 1)
        roi.cell(r, 9).value = econ["npv_usd"]
        updated += 1

    # Refresh TOTAL row I if present
    tot_row = (measure_rows[-1] + 1) if measure_rows else None
    if tot_row and str(roi.cell(tot_row + 1, 1).value or "").upper() == "TOTAL":
        # TOTAL is n+2 in builder (blank line?) — builder uses tot = n+2 with A=TOTAL
        pass
    for r in range(2, (roi.max_row or 2) + 1):
        if str(roi.cell(r, 1).value or "").upper() == "TOTAL":
            # Leave SUM formula on I if present; else sum caches
            ival = roi.cell(r, 9).value
            if not (isinstance(ival, str) and ival.startswith("=")):
                s = 0.0
                for mr in measure_rows:
                    try:
                        s += float(roi.cell(mr, 9).value or 0)
                    except (TypeError, ValueError):
                        pass
                roi.cell(r, 9).value = round(s, 2)
            break

    wb.save(path)
    # Rewrite manifest formula map
    man_path = path.parent / f"{path.stem}.notebook_manifest.json"
    if man_path.is_file() or True:
        man = summarize_notebook(path)
        man_path.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    return {
        "path": str(path),
        "updated_cells": updated,
        "manifest": str(man_path),
        "inputs_used": {
            "area_ft2": area,
            "elec_rate": elec,
            "gas_rate": gas,
            "discount": disc,
            "escalation": esc,
            "life_years": life,
            "package_cost_per_measure": round(package_cost, 2),
        },
    }


def build_and_save_notebook(
    package_id: str,
    out_dir: Path | str,
    *,
    profile: dict[str, Any] | None = None,
    report: dict[str, Any] | None = None,
    input_overrides: dict[str, Any] | None = None,
    write_manifest: bool = True,
) -> dict[str, Path]:
    pkg = get_notebook_package(package_id)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    xlsx = out_dir / f"{pkg.id}.xlsx"
    wb = build_notebook_workbook(
        pkg, profile=profile, report=report, input_overrides=input_overrides
    )
    save_workbook(wb, xlsx)
    written = {"xlsx": xlsx}
    if write_manifest:
        man = summarize_notebook(xlsx, package=pkg)
        mp = out_dir / f"{pkg.id}.notebook_manifest.json"
        mp.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
        written["manifest"] = mp
    return written


def validate_notebook(path: Path | str) -> dict[str, Any]:
    from openpyxl import load_workbook

    path = Path(path)
    errors: list[str] = []
    warnings: list[str] = []
    if not path.is_file():
        return {"ok": False, "errors": [f"missing file: {path}"], "warnings": []}
    wb = load_workbook(path, data_only=False)
    for name in REQUIRED_SHEETS:
        if name not in wb.sheetnames:
            errors.append(f"missing sheet: {name}")
    defined = set(wb.defined_names.keys())
    for n in INPUT_NAMED_RANGES:
        if n not in defined:
            warnings.append(f"missing named range: {n}")
    # BUG-034: warn when E+ sheet has no savings
    ep_filled = 0
    ep_rows = 0
    if "EPlus_Results" in wb.sheetnames:
        for row in wb["EPlus_Results"].iter_rows(min_row=2, max_col=3, values_only=True):
            if not row[0]:
                continue
            ep_rows += 1
            if row[1] is not None or row[2] is not None:
                ep_filled += 1
    if ep_rows and ep_filled == 0:
        warnings.append(
            "EPlus_Results empty (no savings_by_measure) — Compare lights will be YELLOW; "
            "pick a Twin ECM run with measure savings"
        )
    # Honesty: cost B should reference H when still formula-linked
    if "ROI_Capital" in wb.sheetnames:
        b2 = wb["ROI_Capital"]["B2"].value
        h2 = wb["ROI_Capital"]["H2"].value
        if isinstance(b2, (int, float)) and isinstance(h2, str) and h2.startswith("="):
            warnings.append(
                "ROI_Capital!B2 is a static cost while H2 is an Inputs formula — "
                "prefer B=H so yellow Inputs move package cost (BUG-035)"
            )
    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "sheets": list(wb.sheetnames),
        "ep_measure_rows": ep_rows,
        "ep_filled_rows": ep_filled,
    }


def summarize_notebook(path: Path | str, *, package: NotebookPackage | None = None) -> dict[str, Any]:
    from openpyxl import load_workbook

    path = Path(path)
    wb = load_workbook(path, data_only=False)
    measures: list[str] = []
    if "ESCO_Calcs" in wb.sheetnames:
        ws = wb["ESCO_Calcs"]
        for row in ws.iter_rows(min_row=2, max_col=1, values_only=True):
            if row[0]:
                measures.append(str(row[0]))
    verdicts: list[dict[str, str]] = []
    if "Compare" in wb.sheetnames:
        ws = wb["Compare"]
        for row in ws.iter_rows(min_row=2, max_col=9, values_only=True):
            if row[0]:
                verdicts.append(
                    {
                        "measure_id": str(row[0]),
                        "verdict": str(row[7] or ""),
                        "light": str(row[8] or ""),
                    }
                )
    gate = None
    if "Guardrails" in wb.sheetnames:
        gate = wb["Guardrails"]["B2"].value
    inputs: dict[str, Any] = {}
    if "Inputs" in wb.sheetnames:
        for row in wb["Inputs"].iter_rows(min_row=2, max_col=2, values_only=True):
            if row[0]:
                inputs[str(row[0])] = row[1]
    # Prefer package from Cover / stem; load catalog label when possible
    pkg_id = package.id if package else path.stem
    pkg_label = package.label if package else None
    if package is None:
        try:
            package = get_notebook_package(path.stem)
            pkg_id = package.id
            pkg_label = package.label
        except Exception:
            pass
    validated = validate_notebook(path)
    formula_cells = collect_formula_cells(path)
    return {
        "schema": "wattlab_notebook_manifest_v1",
        "path": str(path.resolve()),
        "package_id": pkg_id,
        "package_label": pkg_label,
        "sheets": list(wb.sheetnames),
        "named_ranges": list(wb.defined_names.keys()),
        "measure_ids": measures,
        "compare": verdicts,
        "guardrail_verdict": gate,
        "inputs": inputs,
        "formula_cells": formula_cells,
        "docs_url": ESCO_DOCS_URL,
        "validated": validated,
        "ep_coverage": {
            "measure_rows": validated.get("ep_measure_rows"),
            "filled_rows": validated.get("ep_filled_rows"),
        },
        "honesty": {
            "esco_kwh_therms": "baked_at_build",
            "roi_cost_npv": "excel_formulas_from_inputs",
            "template_file": "scaffold_only",
        },
    }


def preview_sheet_rows(
    path: Path | str,
    sheet: str,
    *,
    max_rows: int = 40,
    data_only: bool = False,
) -> list[list[Any]]:
    """Preview sheet rows for Studio / agents.

    Default ``data_only=False`` so formulas appear as strings and static caches
    (e.g. npv_usd_at_build) remain readable — openpyxl never evaluates Excel (BUG-031).
    """
    from openpyxl import load_workbook

    wb = load_workbook(path, data_only=data_only)
    if sheet not in wb.sheetnames:
        return []
    ws = wb[sheet]
    rows: list[list[Any]] = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i >= max_rows:
            break
        rows.append(list(row))
    return rows


def write_template_stub(path: Path | str) -> Path:
    """Generate a blank package template (controls_first scaffold) for repo templates/."""
    pkg = get_notebook_package("controls_first")
    wb = build_notebook_workbook(pkg, profile={"floor_area_ft2": 50000})
    return save_workbook(wb, path)


__all__ = [
    "build_and_save_notebook",
    "build_notebook_workbook",
    "collect_formula_cells",
    "default_inputs_from_profile",
    "list_notebook_packages",
    "prefill_notebook_inputs",
    "preview_sheet_rows",
    "read_notebook_inputs",
    "refresh_notebook_caches",
    "save_workbook",
    "show_formulas",
    "summarize_notebook",
    "validate_notebook",
    "write_template_stub",
]
