"""Modeled vs actual monthly fuel overlays for Twin Inspect."""

from __future__ import annotations

from typing import Any


_OBS_KWH = (
    "observed_kwh",
    "bill_kwh",
    "bills_kwh",
    "actual_kwh",
    "utility_kwh",
    "kwh_observed",
    "kwh_bill",
)
_MOD_KWH = (
    "modeled_kwh",
    "simulated_kwh",
    "model_kwh",
    "sim_kwh",
    "eplus_kwh",
    "kwh_modeled",
    "kwh_simulated",
)
_OBS_THERM = (
    "observed_therms",
    "bill_therms",
    "bills_therms",
    "actual_therms",
    "utility_therms",
    "therms_observed",
    "therms_bill",
)
_MOD_THERM = (
    "modeled_therms",
    "simulated_therms",
    "model_therms",
    "sim_therms",
    "eplus_therms",
    "therms_modeled",
    "therms_simulated",
)


def _safe_float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _first_present(row: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for k in keys:
        if k in row and row.get(k) is not None and row.get(k) != "":
            return _safe_float(row.get(k))
    return None


def normalize_per_month_rows(
    rows: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Canonical ``observed_*`` / ``modeled_*`` keys for plotting and %‑off."""
    out: list[dict[str, Any]] = []
    for raw in rows or []:
        if not isinstance(raw, dict):
            continue
        row = dict(raw)
        month = row.get("month") or row.get("period") or row.get("YYYY-MM")
        if month is not None:
            row["month"] = str(month)

        obs_k = _first_present(row, _OBS_KWH)
        mod_k = _first_present(row, _MOD_KWH)
        if obs_k is not None:
            row["observed_kwh"] = obs_k
        if mod_k is not None:
            row["modeled_kwh"] = mod_k
            row.setdefault("simulated_kwh", mod_k)

        obs_t = _first_present(row, _OBS_THERM)
        mod_t = _first_present(row, _MOD_THERM)
        if obs_t is not None:
            row["observed_therms"] = obs_t
        if mod_t is not None:
            row["modeled_therms"] = mod_t
            row.setdefault("simulated_therms", mod_t)

        out.append(row)
    return out


def has_fuel_pairs(rows: list[dict[str, Any]], *, fuel: str) -> bool:
    rows = normalize_per_month_rows(rows)
    if fuel == "elec":
        return any(
            r.get("observed_kwh") is not None and r.get("modeled_kwh") is not None for r in rows
        )
    return any(
        r.get("observed_therms") is not None and r.get("modeled_therms") is not None for r in rows
    )


def build_modeled_vs_actual_figure(
    rows: list[dict[str, Any]] | None,
    *,
    fuel: str,
    title: str | None = None,
):
    """Plotly lines: bills vs model for one fuel. None when no month pairs."""
    import plotly.graph_objects as go

    from wattlab.studio.eui_charts import month_abbrev

    rows = normalize_per_month_rows(rows)
    xs: list[str] = []
    obs: list[float] = []
    mod: list[float] = []
    for r in rows:
        if fuel == "elec":
            o, m = r.get("observed_kwh"), r.get("modeled_kwh")
            y_title = "kWh"
            default_title = "Monthly electricity — bills vs model"
        else:
            o, m = r.get("observed_therms"), r.get("modeled_therms")
            y_title = "therms"
            default_title = "Monthly gas — bills vs model"
        if o is None or m is None:
            continue
        mo = str(r.get("month") or "")
        if len(mo) >= 7 and mo[4] == "-":
            lab = f"{mo[:4]}-{month_abbrev(mo[5:7])}"
        elif mo.isdigit():
            lab = month_abbrev(mo)
        else:
            lab = mo or "?"
        xs.append(lab)
        obs.append(float(o))
        mod.append(float(m))
    if not xs:
        return None

    fig = go.Figure()
    fig.add_scatter(
        x=xs,
        y=obs,
        mode="lines+markers",
        name="Bills (observed)",
        line=dict(color="#1f77b4", width=2),
        marker=dict(size=7),
    )
    fig.add_scatter(
        x=xs,
        y=mod,
        mode="lines+markers",
        name="Model (EnergyPlus)",
        line=dict(color="#d62728" if fuel == "elec" else "#2ca02c", width=2),
        marker=dict(size=7),
    )
    fig.update_layout(
        title=title or default_title,
        height=380,
        margin=dict(l=48, r=16, t=48, b=48),
        yaxis_title=y_title,
        xaxis_title="Month",
        legend=dict(orientation="h", y=1.12),
        font=dict(size=12),
    )
    return fig


__all__ = [
    "build_modeled_vs_actual_figure",
    "has_fuel_pairs",
    "normalize_per_month_rows",
]
