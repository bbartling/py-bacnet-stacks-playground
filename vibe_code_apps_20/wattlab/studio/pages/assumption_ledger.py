"""Assumption Ledger — provenance for model inputs and dump gaps (read-only)."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from wattlab.seed import gap_report

_SOURCE_CLASS = {
    "user": "HUMAN",
    "default": "DEFAULTED",
    "vibe19": "MEASURED",
    "inferred": "INFERRED",
    "measured": "MEASURED",
    "human": "HUMAN",
    "missing": "MISSING",
}


def _map_source(raw: str | None) -> str:
    if not raw:
        return "DEFAULTED"
    return _SOURCE_CLASS.get(str(raw).strip().lower(), str(raw).upper())


def _rows_from_field_sources(profile: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not profile:
        return []
    fs = profile.get("field_sources") or {}
    rows: list[dict[str, Any]] = []
    for field, meta in sorted(fs.items()):
        if not isinstance(meta, dict):
            rows.append(
                {
                    "field": field,
                    "value": meta,
                    "unit": "",
                    "source_class": "DEFAULTED",
                    "confidence_status": "unknown",
                    "notes": "",
                }
            )
            continue
        rows.append(
            {
                "field": field,
                "value": meta.get("value"),
                "unit": meta.get("unit") or "",
                "source_class": _map_source(meta.get("source")),
                "confidence_status": str(meta.get("source") or "unknown"),
                "notes": meta.get("note") or "",
            }
        )
    return rows


def _rows_from_gaps(bundle: Any) -> list[dict[str, Any]]:
    if bundle is None:
        return []
    rows: list[dict[str, Any]] = []
    for g in gap_report(bundle):
        status = str(g.get("status") or "")
        if status == "ok":
            continue
        sev = str(g.get("severity") or "")
        rows.append(
            {
                "field": g.get("field"),
                "value": g.get("value"),
                "unit": "",
                "source_class": "MISSING" if status == "missing" else status.upper(),
                "confidence_status": sev or status,
                "notes": g.get("why") or "",
            }
        )
    return rows


def _rows_from_hypothesis(result: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not result:
        return []
    assumptions = result.get("assumptions") or result.get("assumption_register") or []
    rows: list[dict[str, Any]] = []
    if isinstance(assumptions, list):
        for a in assumptions:
            if not isinstance(a, dict):
                continue
            rows.append(
                {
                    "field": a.get("name") or a.get("field"),
                    "value": a.get("value"),
                    "unit": a.get("units") or a.get("unit") or "",
                    "source_class": _map_source(
                        str(a.get("provenance") or a.get("source") or "default")
                    ),
                    "confidence_status": str(a.get("confidence") or "low"),
                    "notes": a.get("rationale") or a.get("notes") or "Hypothesis Lab",
                }
            )
    return rows


def render(
    *,
    profile: dict[str, Any] | None = None,
    bundle: Any = None,
    hypothesis_result: dict[str, Any] | None = None,
) -> None:
    st.header("Assumption Ledger — where every number came from")
    st.caption(
        "Read-only provenance view. Source classes: MEASURED / INFERRED / DEFAULTED / "
        "HUMAN / MISSING. Edit inputs on Model or Hypothesis Lab — this page never "
        "silently changes the project."
    )

    rows = (
        _rows_from_field_sources(profile)
        + _rows_from_gaps(bundle)
        + _rows_from_hypothesis(hypothesis_result)
    )

    if not rows:
        st.info(
            "No ledger rows yet. Resolve a profile on Model, load a dump on Ingest, "
            "or run Hypothesis Lab to populate provenance."
        )
        return

    df = pd.DataFrame(rows)
    # Stable column order; stringify value for Arrow-safe Streamlit display.
    cols = ["field", "value", "unit", "source_class", "confidence_status", "notes"]
    df = df.reindex(columns=cols)
    df["value"] = df["value"].map(lambda v: "" if v is None else str(v))
    df["unit"] = df["unit"].fillna("").astype(str)
    df["notes"] = df["notes"].fillna("").astype(str)

    counts = df["source_class"].value_counts().to_dict()
    metrics = st.columns(min(5, max(1, len(counts))))
    for i, (klass, n) in enumerate(sorted(counts.items())):
        metrics[i % len(metrics)].metric(str(klass), str(n))

    filt = st.multiselect(
        "Filter source class",
        sorted(df["source_class"].dropna().unique().tolist()),
        default=sorted(df["source_class"].dropna().unique().tolist()),
        key="assumption_ledger_filter",
    )
    view = df[df["source_class"].isin(filt)] if filt else df
    st.dataframe(view, width="stretch", hide_index=True)
