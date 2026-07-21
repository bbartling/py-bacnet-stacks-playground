"""EUI index helpers — bills vs peer bands vs EnergyPlus model (Studio)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from wattlab.benchmarks.eui import compare_eui, lookup
from wattlab.config import PROTOTYPE_AREA_FT2_NOMINAL


def _annual_from_report(report: dict[str, Any] | None) -> dict[str, Any]:
    if not report:
        return {}
    for key in ("baseline_annual", "annual"):
        block = report.get(key)
        if isinstance(block, dict) and block:
            return block
    records = report.get("result_records") or report.get("records") or []
    for rr in records:
        if rr.get("measure_id") in (None, "", "baseline"):
            ann = rr.get("annual") or {}
            if ann:
                return ann
    if records:
        return dict((records[0] or {}).get("annual") or {})
    return {}


def load_model_eui_from_run(run_dir: Path | None) -> dict[str, Any]:
    """Pull model site EUI + scale stamps from a published ``runs/<id>/`` tree."""
    out: dict[str, Any] = {}
    if run_dir is None or not Path(run_dir).is_dir():
        return out
    root = Path(run_dir)
    for name in ("report.json", "wattlab_report.json", "campaign_stamp.json"):
        p = root / name
        if not p.is_file():
            continue
        try:
            report = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        ann = _annual_from_report(report)
        eui = ann.get("site_eui_kbtu_ft2_year")
        if eui is None:
            eui = report.get("site_eui_kbtu_ft2_year") or report.get("site_eui_kbtu_ft2")
        if eui is not None:
            out["model_eui_kbtu_ft2"] = float(eui)
        out["building_area_m2"] = ann.get("building_area_m2") or report.get("building_area_m2")
        out["prototype_area_scale"] = report.get("prototype_area_scale")
        out["target_floor_area_ft2"] = report.get("target_floor_area_ft2")
        out["area_honesty"] = report.get("area_honesty")
        out["weather_mode"] = (
            (report.get("weather_suitability") or {}).get("mode")
            or report.get("weather_mode")
        )
        if ann.get("peak_demand_kw") is not None:
            out["peak_demand_kw"] = ann.get("peak_demand_kw")
        out["run_id"] = report.get("run_id") or root.name
        if out.get("model_eui_kbtu_ft2") is not None:
            return out
    return out


def build_eui_index(
    *,
    bill_eui_kbtu_ft2: float | None,
    property_type: str,
    model_eui_kbtu_ft2: float | None = None,
    prototype_area_scale: float | None = None,
    target_floor_area_ft2: float | None = None,
    model_label: str = "EnergyPlus model",
) -> dict[str, Any]:
    """Compare bill / peer / model EUIs for Studio tables + charts.

    Model EUI from 5Zone is on **prototype** area (~10k ft²). Absolute kWh must
    not be compared to site bills without ``prototype_area_scale``; EUI
    (intensity) can still be plotted beside peers as a screening index.
    """
    ptype = property_type or "office"
    bm = lookup(ptype)
    p20 = float(bm.get("p20") or float(bm["p50"]) * 0.65)
    p50 = float(bm["p50"])
    p80 = float(bm.get("p80") or float(bm["p50"]) * 1.35)
    rows: list[dict[str, Any]] = []
    if bill_eui_kbtu_ft2 is not None:
        bill_cmp = compare_eui(float(bill_eui_kbtu_ft2), ptype)
        rows.append(
            {
                "series": "Bills (site)",
                "site_eui_kbtu_ft2": bill_cmp["site_eui_kbtu_ft2"],
                "band": bill_cmp["band"],
                "vs_median_pct": bill_cmp["vs_median_pct"],
                "note": "Measured / allocated campus bills",
            }
        )
    rows.append(
        {
            "series": "Peer p20",
            "site_eui_kbtu_ft2": p20,
            "band": "peer",
            "vs_median_pct": None,
            "note": bm.get("source") or "benchmark registry",
        }
    )
    rows.append(
        {
            "series": "Peer p50 (typical)",
            "site_eui_kbtu_ft2": p50,
            "band": "peer",
            "vs_median_pct": 0.0,
            "note": bm.get("benchmark_name") or bm.get("source"),
        }
    )
    rows.append(
        {
            "series": "Peer p80",
            "site_eui_kbtu_ft2": p80,
            "band": "peer",
            "vs_median_pct": None,
            "note": bm.get("source") or "benchmark registry",
        }
    )
    if model_eui_kbtu_ft2 is not None:
        model_cmp = compare_eui(float(model_eui_kbtu_ft2), ptype)
        scale = float(prototype_area_scale) if prototype_area_scale else None
        note = (
            f"{model_label} on prototype footprint (~{PROTOTYPE_AREA_FT2_NOMINAL:,.0f} ft²)"
        )
        if target_floor_area_ft2:
            note += f"; target site {float(target_floor_area_ft2):,.0f} ft²"
        if scale and scale > 1.05:
            note += f"; scale≈{scale:.2f}× — do not treat raw kWh as site total"
        rows.append(
            {
                "series": "Model (prototype EUI)",
                "site_eui_kbtu_ft2": model_cmp["site_eui_kbtu_ft2"],
                "band": model_cmp["band"],
                "vs_median_pct": model_cmp["vs_median_pct"],
                "note": note,
            }
        )
    return {
        "property_type": bm.get("property_type") or ptype,
        "property_type_matched": bm.get("property_type_matched"),
        "peer_p20": p20,
        "peer_p50": p50,
        "peer_p80": p80,
        "benchmark_name": bm.get("benchmark_name"),
        "source": bm.get("source"),
        "bill_eui_kbtu_ft2": (
            round(float(bill_eui_kbtu_ft2), 1) if bill_eui_kbtu_ft2 is not None else None
        ),
        "model_eui_kbtu_ft2": (
            round(float(model_eui_kbtu_ft2), 1) if model_eui_kbtu_ft2 is not None else None
        ),
        "prototype_area_scale": prototype_area_scale,
        "rows": rows,
    }
