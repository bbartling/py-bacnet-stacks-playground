"""Parse EnergyPlus tabular outputs into result_record annual fields."""

from __future__ import annotations

import csv
import hashlib
import re
from pathlib import Path
from typing import Any

GJ_TO_KWH = 277.7777777778
MJ_PER_M2_TO_KBTU_PER_FT2 = 0.0879875  # approx


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _parse_float(token: str) -> float | None:
    token = (token or "").strip().strip('"')
    if not token:
        return None
    try:
        return float(token)
    except ValueError:
        return None


def _annual_fields(
    *,
    site_gj: float | None,
    site_mj_m2: float | None,
    elec_gj: float | None,
    gas_gj: float | None,
    area_m2: float | None,
    source_file: Path,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "total_site_energy_gj": site_gj,
        "total_site_energy_mj_per_m2": site_mj_m2,
        "electricity_gj": elec_gj,
        "natural_gas_gj": gas_gj,
        "building_area_m2": area_m2,
        "source_file": str(source_file),
    }
    if elec_gj is not None:
        out["electricity_kwh_year"] = round(elec_gj * GJ_TO_KWH, 2)
    if gas_gj is not None:
        out["natural_gas_kwh_equiv_year"] = round(gas_gj * GJ_TO_KWH, 2)
        out["natural_gas_therm_year"] = round(gas_gj * 9.4804, 2)
    if site_mj_m2 is not None:
        out["site_eui_kbtu_ft2_year"] = round(site_mj_m2 * MJ_PER_M2_TO_KBTU_PER_FT2, 2)
    elif site_gj is not None and area_m2 and area_m2 > 0:
        mj_m2 = (site_gj * 1000.0) / area_m2
        out["site_eui_kbtu_ft2_year"] = round(mj_m2 * MJ_PER_M2_TO_KBTU_PER_FT2, 2)
    return out


def parse_eplustbl_csv(path: Path) -> dict[str, Any]:
    """Extract site energy + end-use totals from eplustbl.csv."""
    text = path.read_text(encoding="utf-8", errors="replace")
    site_gj: float | None = None
    site_mj_m2: float | None = None
    elec_gj: float | None = None
    gas_gj: float | None = None
    area_m2: float | None = None

    for raw in text.splitlines():
        parts = [p.strip() for p in raw.split(",")]
        if len(parts) >= 3 and parts[1] == "Total Site Energy" and site_gj is None:
            site_gj = _parse_float(parts[2])
            if len(parts) >= 4:
                site_mj_m2 = _parse_float(parts[3])
        elif len(parts) >= 3 and parts[1] == "Total Building Area" and area_m2 is None:
            area_m2 = _parse_float(parts[2])
        elif len(parts) >= 3 and parts[1] == "Net Conditioned Building Area":
            v = _parse_float(parts[2])
            if v and v > 0:
                area_m2 = v
        elif len(parts) >= 3 and parts[1] == "Total End Uses" and elec_gj is None:
            # First "Total End Uses" is Annual Building Utility Performance (GJ).
            # Later tables reuse the label for demand (W) — ignore those.
            elec_gj = _parse_float(parts[2])
            if len(parts) >= 4:
                gas_gj = _parse_float(parts[3])

    facility_gj: float | None = None
    for raw in text.splitlines():
        parts = [p.strip() for p in raw.split(",")]
        if len(parts) >= 3 and parts[1] == "Electricity:Facility":
            facility_gj = _parse_float(parts[2])
            break

    if elec_gj is None:
        elec_gj = facility_gj
    # Prefer Facility meter when present and sane vs demand-table pollution
    if facility_gj is not None and (elec_gj is None or elec_gj > facility_gj * 50):
        elec_gj = facility_gj


    return _annual_fields(
        site_gj=site_gj,
        site_mj_m2=site_mj_m2,
        elec_gj=elec_gj,
        gas_gj=gas_gj,
        area_m2=area_m2,
        source_file=path,
    )


def parse_eplustbl_htm(path: Path) -> dict[str, Any]:
    """Extract key annuals from eplustbl.htm when CSV was not requested."""
    text = path.read_text(encoding="utf-8", errors="replace")

    def row_vals(label: str) -> list[float]:
        m = re.search(
            rf'<td[^>]*>\s*{re.escape(label)}\s*</td>(.*?)</tr>',
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if not m:
            return []
        return [
            float(x)
            for x in re.findall(r'<td[^>]*>\s*([0-9.]+)\s*</td>', m.group(1))
        ]

    site_vals = row_vals("Total Site Energy")
    end_vals = row_vals("Total End Uses")
    area_vals = row_vals("Total Building Area")
    cond_vals = row_vals("Net Conditioned Building Area")
    area_m2 = None
    if cond_vals and cond_vals[0] > 0:
        area_m2 = cond_vals[0]
    elif area_vals:
        area_m2 = area_vals[0]
    return _annual_fields(
        site_gj=site_vals[0] if site_vals else None,
        site_mj_m2=site_vals[1] if len(site_vals) > 1 else None,
        elec_gj=end_vals[0] if end_vals else None,
        gas_gj=end_vals[1] if len(end_vals) > 1 else None,
        area_m2=area_m2,
        source_file=path,
    )

def parse_end_file(path: Path) -> dict[str, Any]:
    """Parse eplusout.end for success / fatal."""
    if not path.is_file():
        return {"ok": False, "raw": ""}
    raw = path.read_text(encoding="utf-8", errors="replace")
    ok = "EnergyPlus Completed Successfully" in raw or re.search(
        r"EnergyPlus Completed Successfully", raw, re.I
    )
    return {"ok": bool(ok), "raw": raw.strip()}


_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def parse_monthly_energy(path: Path) -> list[dict[str, Any]]:
    """
    Extract monthly electricity / gas from eplustbl.csv BUILDING ENERGY PERFORMANCE
    - ELECTRICITY / NATURAL GAS style tables when present.

    Falls back to empty list if tables are missing (HTML-only or alternate report style).
    """
    if not path.is_file() or path.suffix.lower() not in {".csv", ".htm", ".html"}:
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() == ".csv":
        return _parse_monthly_from_csv_text(text)
    return _parse_monthly_from_htm_text(text)


def _parse_monthly_from_csv_text(text: str) -> list[dict[str, Any]]:
    """
    EnergyPlus CSV report often has rows like:
      ,January,.... or MONTH,Electricity [GJ],...
    We look for month-name rows with numeric columns after a header that mentions
    ELECTRICITY or Natural Gas under Building Energy Performance.
    """
    monthly: dict[str, dict[str, float | None]] = {
        m: {"electricity_gj": None, "natural_gas_gj": None} for m in _MONTHS
    }
    lines = [ln.strip() for ln in text.splitlines()]
    # Scan for "BUILDING ENERGY PERFORMANCE - ELECTRICITY" then month rows
    mode: str | None = None
    for ln in lines:
        up = ln.upper()
        if "BUILDING ENERGY PERFORMANCE" in up and "ELECTRICITY" in up:
            mode = "elec"
            continue
        if "BUILDING ENERGY PERFORMANCE" in up and (
            "NATURAL GAS" in up or "GAS" in up
        ):
            mode = "gas"
            continue
        if mode and ln.startswith(",") is False and not ln:
            mode = None
            continue
        parts = [p.strip().strip('"') for p in ln.split(",")]
        if not parts:
            continue
        month = parts[0] if parts[0] in _MONTHS else (parts[1] if len(parts) > 1 and parts[1] in _MONTHS else None)
        if not month or mode is None:
            # also handle ",January,val,..."
            if len(parts) > 1 and parts[1] in _MONTHS:
                month = parts[1]
            else:
                continue
        # Total column is often last numeric before Annual, or column titled Total Energy
        nums = [_parse_float(p) for p in parts]
        nums = [n for n in nums if n is not None]
        if not nums:
            continue
        total = nums[-1]
        if mode == "elec":
            monthly[month]["electricity_gj"] = total
        elif mode == "gas":
            monthly[month]["natural_gas_gj"] = total

    out: list[dict[str, Any]] = []
    for i, m in enumerate(_MONTHS, start=1):
        row = monthly[m]
        elec_gj = row["electricity_gj"]
        gas_gj = row["natural_gas_gj"]
        entry: dict[str, Any] = {"month": i, "month_name": m}
        if elec_gj is not None:
            entry["electricity_gj"] = elec_gj
            entry["electricity_kwh"] = round(elec_gj * GJ_TO_KWH, 2)
        if gas_gj is not None:
            entry["natural_gas_gj"] = gas_gj
            entry["natural_gas_therm"] = round(gas_gj * 9.4804, 2)
        if "electricity_kwh" in entry or "natural_gas_therm" in entry:
            out.append(entry)
    return out


def _parse_monthly_from_htm_text(text: str) -> list[dict[str, Any]]:
    """Best-effort HTML scrape of monthly building energy performance tables."""
    monthly: dict[str, dict[str, float | None]] = {
        m: {"electricity_gj": None, "natural_gas_gj": None} for m in _MONTHS
    }
    # Find table sections by caption / heading
    for kind, key in (("ELECTRICITY", "electricity_gj"), ("NATURAL GAS", "natural_gas_gj")):
        m = re.search(
            rf"BUILDING ENERGY PERFORMANCE\s*[-–]\s*{kind}(.*?)(?:BUILDING ENERGY PERFORMANCE|Report:|\Z)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        block = m.group(1) if m else text
        for month in _MONTHS:
            rm = re.search(
                rf"<td[^>]*>\s*{month}\s*</td>(.*?)</tr>",
                block,
                re.IGNORECASE | re.DOTALL,
            )
            if not rm:
                continue
            vals = [
                float(x)
                for x in re.findall(r"<td[^>]*>\s*([0-9.]+)\s*</td>", rm.group(1))
            ]
            if vals:
                monthly[month][key] = vals[-1]

    out: list[dict[str, Any]] = []
    for i, mname in enumerate(_MONTHS, start=1):
        row = monthly[mname]
        entry: dict[str, Any] = {"month": i, "month_name": mname}
        if row["electricity_gj"] is not None:
            entry["electricity_gj"] = row["electricity_gj"]
            entry["electricity_kwh"] = round(row["electricity_gj"] * GJ_TO_KWH, 2)
        if row["natural_gas_gj"] is not None:
            entry["natural_gas_gj"] = row["natural_gas_gj"]
            entry["natural_gas_therm"] = round(row["natural_gas_gj"] * 9.4804, 2)
        if "electricity_kwh" in entry or "natural_gas_therm" in entry:
            out.append(entry)
    return out


def annual_from_output_dir(
    output_dir: Path,
    *,
    elec_rate_usd_per_kwh: float = 0.12,
    gas_rate_usd_per_therm: float = 0.80,
) -> dict[str, Any]:
    csv_path = output_dir / "eplustbl.csv"
    htm_path = output_dir / "eplustbl.htm"
    end_path = output_dir / "eplusout.end"
    end = parse_end_file(end_path)
    if csv_path.is_file():
        parsed = parse_eplustbl_csv(csv_path)
        monthly = parse_monthly_energy(csv_path)
    elif htm_path.is_file():
        parsed = parse_eplustbl_htm(htm_path)
        parsed.setdefault("quality_flags", [])
        monthly = parse_monthly_energy(htm_path)
    else:
        return {
            "ok": False,
            "status": "MODEL_RUN_FAILED",
            "quality_flags": ["missing_eplustbl"],
            "end": end,
            "monthly": [],
        }
    cost = 0.0
    if parsed.get("electricity_kwh_year") is not None:
        cost += parsed["electricity_kwh_year"] * elec_rate_usd_per_kwh
    if parsed.get("natural_gas_therm_year") is not None:
        cost += parsed["natural_gas_therm_year"] * gas_rate_usd_per_therm
    parsed["utility_cost_usd_year"] = round(cost, 2)
    parsed["ok"] = bool(end.get("ok"))
    parsed["status"] = "COMPLETE" if parsed["ok"] else "MODEL_RUN_FAILED"
    parsed["quality_flags"] = [] if parsed["ok"] else ["energyplus_end_not_success"]
    parsed["end"] = end
    parsed["monthly"] = monthly
    return parsed


def _delta(before: float | None, after: float | None) -> float | None:
    if before is None or after is None:
        return None
    return round(before - after, 2)


def _pct(before: float | None, after: float | None) -> float | None:
    if before is None or after is None or before == 0:
        return None
    return round(100.0 * (before - after) / before, 2)


def savings_by_measure(result_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Progressive savings table mirroring progressive Results.
    First record is baseline (measure_id None); each subsequent row vs baseline
    and vs previous step.
    """
    if not result_records:
        return []
    baseline = result_records[0].get("annual") or {}
    prev = baseline
    rows: list[dict[str, Any]] = []
    for i, rec in enumerate(result_records):
        ann = rec.get("annual") or {}
        mid = rec.get("measure_id")
        row = {
            "step": i,
            "measure_id": mid or "baseline",
            "electricity_kwh_year": ann.get("electricity_kwh_year"),
            "natural_gas_therm_year": ann.get("natural_gas_therm_year"),
            "site_eui_kbtu_ft2_year": ann.get("site_eui_kbtu_ft2_year"),
            "utility_cost_usd_year": ann.get("utility_cost_usd_year"),
            "vs_baseline": {
                "kwh_saved": _delta(
                    baseline.get("electricity_kwh_year"), ann.get("electricity_kwh_year")
                ),
                "therms_saved": _delta(
                    baseline.get("natural_gas_therm_year"),
                    ann.get("natural_gas_therm_year"),
                ),
                "cost_saved_usd": _delta(
                    baseline.get("utility_cost_usd_year"),
                    ann.get("utility_cost_usd_year"),
                ),
                "eui_delta": _delta(
                    baseline.get("site_eui_kbtu_ft2_year"),
                    ann.get("site_eui_kbtu_ft2_year"),
                ),
                "kwh_pct": _pct(
                    baseline.get("electricity_kwh_year"), ann.get("electricity_kwh_year")
                ),
            },
            "vs_previous": {
                "kwh_saved": _delta(
                    prev.get("electricity_kwh_year"), ann.get("electricity_kwh_year")
                ),
                "therms_saved": _delta(
                    prev.get("natural_gas_therm_year"), ann.get("natural_gas_therm_year")
                ),
                "cost_saved_usd": _delta(
                    prev.get("utility_cost_usd_year"), ann.get("utility_cost_usd_year")
                ),
                "kwh_pct": _pct(
                    prev.get("electricity_kwh_year"), ann.get("electricity_kwh_year")
                ),
            },
        }
        rows.append(row)
        prev = ann
    return rows


def build_result_record(
    *,
    run_id: str,
    measure_id: str | None,
    idf_path: Path,
    annual: dict[str, Any],
    artifacts: list[str] | None = None,
    extra_flags: list[str] | None = None,
) -> dict[str, Any]:
    flags = list(annual.get("quality_flags") or [])
    if extra_flags:
        flags.extend(extra_flags)
    return {
        "run_id": run_id,
        "measure_id": measure_id,
        "input_hash": file_sha256(idf_path) if idf_path.is_file() else "",
        "status": annual.get("status") or "RESULTS_SUSPECT",
        "annual": {
            "electricity_kwh_year": annual.get("electricity_kwh_year"),
            "natural_gas_therm_year": annual.get("natural_gas_therm_year"),
            "site_eui_kbtu_ft2_year": annual.get("site_eui_kbtu_ft2_year"),
            "utility_cost_usd_year": annual.get("utility_cost_usd_year"),
            "total_site_energy_gj": annual.get("total_site_energy_gj"),
        },
        "monthly": list(annual.get("monthly") or []),
        "quality_flags": flags,
        "artifacts": artifacts or [],
    }
