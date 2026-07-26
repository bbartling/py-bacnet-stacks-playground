"""Monthly model-vs-bills percent-off analytics for Twin Inspect."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from wattlab.studio.eui_charts import month_abbrev

# Default "OK-ish" band (±%) for month-by-month narratives
DEFAULT_OK_BAND_PCT = 15.0


def _safe_float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def month_short_label(month_key: Any) -> str:
    """``2024-12`` / ``12`` / ``Dec`` → short month label for narratives."""
    s = str(month_key or "").strip()
    if not s:
        return "?"
    if len(s) >= 7 and s[4] == "-" and s[5:7].isdigit():
        return month_abbrev(s[5:7])
    if s.isdigit() and 1 <= int(s) <= 12:
        return month_abbrev(s)
    if len(s) >= 3 and s[:3].isalpha():
        return s[:3].title()
    return s


def pct_off(modeled: float | None, observed: float | None) -> float | None:
    """(model − bill) / bill × 100. Positive = model too high."""
    if modeled is None or observed is None:
        return None
    if abs(observed) < 1e-9:
        return None
    return (float(modeled) - float(observed)) / float(observed) * 100.0


def _pair_from_row(row: dict[str, Any], fuel: str) -> tuple[float | None, float | None]:
    from wattlab.studio.monthly_fuel_chart import normalize_per_month_rows

    norm = normalize_per_month_rows([row])
    r = norm[0] if norm else row
    if fuel == "elec":
        obs = _safe_float(r.get("observed_kwh"))
        sim = _safe_float(r.get("modeled_kwh") if r.get("modeled_kwh") is not None else r.get("simulated_kwh"))
        return sim, obs
    obs = _safe_float(r.get("observed_therms"))
    sim = _safe_float(
        r.get("modeled_therms") if r.get("modeled_therms") is not None else r.get("simulated_therms")
    )
    return sim, obs


def _fmt_signed(pct: float) -> str:
    # Unicode minus for under, plus for over
    if pct >= 0:
        return f"+{pct:.0f}%"
    return f"−{abs(pct):.0f}%"


def _fmt_list(items: list[tuple[str, float]]) -> str:
    if not items:
        return ""
    return ", ".join(f"{lab} {_fmt_signed(p)}" for lab, p in items)


def analyze_fuel_months(
    per_month: list[dict[str, Any]],
    *,
    fuel: str,
    ok_band_pct: float = DEFAULT_OK_BAND_PCT,
) -> dict[str, Any]:
    """Bucket months into over / under / ok for one fuel."""
    over: list[tuple[str, float]] = []
    under: list[tuple[str, float]] = []
    ok: list[tuple[str, float]] = []
    for row in per_month:
        if not isinstance(row, dict):
            continue
        sim, obs = _pair_from_row(row, fuel)
        pct = pct_off(sim, obs)
        if pct is None:
            continue
        lab = month_short_label(row.get("month") or row.get("period"))
        if pct > ok_band_pct:
            over.append((lab, pct))
        elif pct < -ok_band_pct:
            under.append((lab, pct))
        else:
            ok.append((lab, pct))
    return {
        "fuel": fuel,
        "ok_band_pct": ok_band_pct,
        "over": over,
        "under": under,
        "ok": ok,
        "n": len(over) + len(under) + len(ok),
    }


def format_fuel_narrative(bucket: dict[str, Any], *, label: str) -> str:
    """Human analytics blurb for one fuel (elec or gas)."""
    over = bucket.get("over") or []
    under = bucket.get("under") or []
    ok = bucket.get("ok") or []
    band = float(bucket.get("ok_band_pct") or DEFAULT_OK_BAND_PCT)
    n = int(bucket.get("n") or 0)
    if n == 0:
        return f"{label}: no monthly model↔bill pairs in this scorecard."

    lines: list[str] = []
    # Prefer "mostly within" when outliers are few
    outliers = over + under
    if outliers and len(outliers) <= max(3, n // 4) and len(ok) >= n // 2:
        except_txt = _fmt_list(sorted(outliers, key=lambda x: -abs(x[1])))
        lines.append(
            f"{label} is mostly within ~±{band:g}% except {except_txt}."
        )
    else:
        if over:
            lines.append(
                f"{label} over (model too high): {_fmt_list(over)}"
            )
        if under:
            lines.append(
                f"{label} under (model too low): {_fmt_list(under)}"
            )
        if ok:
            ok_txt = ", ".join(f"{lab} ({_fmt_signed(p)})" for lab, p in ok)
            lines.append(f"OK-ish (±{band:g}%): {ok_txt}")
        if not over and not under and ok:
            lines.append(
                f"{label}: all {n} months within ±{band:g}% of bills."
            )
    return "\n".join(lines)


def build_monthly_pct_off(
    per_month: list[dict[str, Any]] | None,
    *,
    ok_band_pct: float = DEFAULT_OK_BAND_PCT,
) -> dict[str, Any]:
    """Full elec + gas monthly % off analysis from scorecard ``per_month`` rows."""
    from wattlab.studio.monthly_fuel_chart import normalize_per_month_rows

    rows = normalize_per_month_rows(list(per_month or []))
    elec = analyze_fuel_months(rows, fuel="elec", ok_band_pct=ok_band_pct)
    gas = analyze_fuel_months(rows, fuel="gas", ok_band_pct=ok_band_pct)
    return {
        "ok_band_pct": ok_band_pct,
        "elec": elec,
        "gas": gas,
        "elec_narrative": format_fuel_narrative(elec, label="Elec"),
        "gas_narrative": format_fuel_narrative(gas, label="Gas"),
        "has_data": bool(elec["n"] or gas["n"]),
    }


def load_per_month_from_run(run_dir: Path | str | None) -> list[dict[str, Any]]:
    """Load ``utility_bills.per_month`` from a published Twin run directory."""
    if not run_dir:
        return []
    root = Path(run_dir)
    if not root.is_dir():
        return []
    for name in ("calibration_scorecard.json", "campaign_stamp.json", "report.json", "wattlab_report.json"):
        path = root / name
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            continue
        if not isinstance(data, dict):
            continue
        if name == "campaign_stamp.json" and data.get("scorecard_path"):
            sp = Path(str(data["scorecard_path"]))
            if sp.is_file():
                try:
                    data = json.loads(sp.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError, TypeError):
                    continue
        ub = data.get("utility_bills") or {}
        if not isinstance(ub, dict):
            # Some reports nest calibration under calibration / g14
            ub = (data.get("calibration") or {}).get("utility_bills") or {}
        rows = ub.get("per_month") if isinstance(ub, dict) else None
        if rows:
            from wattlab.studio.monthly_fuel_chart import normalize_per_month_rows

            out = normalize_per_month_rows(
                [pm for pm in rows if isinstance(pm, dict)]
            )
            if out:
                return out
    return []


def render_monthly_pct_off_panel(
    analysis: dict[str, Any],
    *,
    fuel_filter: str = "both",
    key_prefix: str = "monthly_pct_off",
) -> None:
    """Streamlit panel for Inspect / Modeled-vs-actual.

    ``fuel_filter``: ``elec`` | ``gas`` | ``both`` (default).
    Always surfaces a caption when a requested fuel lacks monthly pairs,
    even if the other fuel (or aggregate G14 stats) look fine.
    """
    import streamlit as st

    if not analysis.get("has_data"):
        st.caption(
            "Monthly % off needs a published scorecard with `utility_bills.per_month` "
            "(observed vs simulated kWh/therms) on this run."
        )
        return
    band = analysis.get("ok_band_pct", DEFAULT_OK_BAND_PCT)
    st.markdown("#### Monthly % off (model vs bills)")
    st.caption(
        f"Percent = (model − bill) / bill × 100. Positive = model too high. "
        f"OK-ish band ±{band:g}%."
    )
    gas_n = (analysis.get("gas") or {}).get("n") or 0
    elec_n = (analysis.get("elec") or {}).get("n") or 0
    want = (fuel_filter or "both").lower().strip()
    show_elec = want in ("elec", "electricity", "both", "all")
    show_gas = want in ("gas", "natural_gas", "ng", "both", "all")

    if show_gas:
        if gas_n:
            st.markdown(analysis.get("gas_narrative") or "")
        else:
            st.info(
                "Gas: no monthly bill↔model pairs in this scorecard "
                "(`observed_therms` + `modeled_therms` / `simulated_therms`). "
                "G14 gas metrics above may still come from annual aggregates."
            )
    if show_elec:
        if elec_n:
            st.markdown(analysis.get("elec_narrative") or "")
        else:
            st.info(
                "Elec: no monthly bill↔model pairs in this scorecard "
                "(`observed_kwh` + `modeled_kwh` / `simulated_kwh`). "
                "G14 elec metrics above may still come from annual aggregates — "
                "that is why PASS can show without an elec monthly ±% panel."
            )

    # Compact table (filtered)
    rows_out: list[dict[str, Any]] = []
    fuels = []
    if show_elec:
        fuels.append(("elec", "Elec"))
    if show_gas:
        fuels.append(("gas", "Gas"))
    for fuel_key, label in fuels:
        b = analysis.get(fuel_key) or {}
        for bucket_name, items in (
            ("over", b.get("over") or []),
            ("under", b.get("under") or []),
            ("ok", b.get("ok") or []),
        ):
            for lab, pct in items:
                rows_out.append(
                    {
                        "fuel": label,
                        "month": lab,
                        "pct_off": round(pct, 1),
                        "bucket": bucket_name,
                    }
                )
    if rows_out:
        import pandas as pd

        st.dataframe(
            pd.DataFrame(rows_out),
            width="stretch",
            hide_index=True,
            height=220,
        )
