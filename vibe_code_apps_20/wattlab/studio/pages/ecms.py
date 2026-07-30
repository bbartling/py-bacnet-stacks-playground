"""ECMs — simple spreadsheet vs EnergyPlus compare (energy, cost, ROI).

Spreadsheet calcs come from external sources / full-parity merge when present.
EnergyPlus side = cascade on best G14 Twin via MCP/DinD simulate.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from wattlab.ecm.compare import (
    compare_path,
    discover_notebook_xlsx,
    empty_compare_stub,
    load_compare,
    merge_full_parity_ss,
    write_compare,
)
from wattlab.ecm.run_on_twin import DEFAULT_G36_ECMS, run_ecms_on_twin
from wattlab.studio.workspace import reports_dir, workspace_root


def _fmt(v: Any) -> str:
    if v is None or v == "":
        return "—"
    if isinstance(v, float):
        if abs(v) >= 100:
            return f"{v:,.0f}"
        return f"{v:,.2f}"
    return str(v)


def _compare_table(payload: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for m in payload.get("measures") or []:
        rows.append(
            {
                "measure": m.get("measure_id"),
                "ss_kWh": m.get("ss_kwh"),
                "ep_kWh": m.get("ep_kwh"),
                "ss_$": m.get("ss_usd"),
                "ep_$": m.get("ep_usd"),
                "capital_$": m.get("capital_usd"),
                "payback_ss_yr": m.get("payback_yr_ss"),
                "payback_ep_yr": m.get("payback_yr_ep"),
                "ROI_ss": m.get("roi_ss"),
                "ROI_ep": m.get("roi_ep"),
                "status": m.get("status"),
            }
        )
    return pd.DataFrame(rows)


def render(*, profile: dict[str, Any] | None = None) -> None:
    st.header("ECMs")
    st.caption(
        "Two columns of truth: **spreadsheet** (full-parity / external ESCO when present) vs "
        "**EnergyPlus** (best calibrated Twin + MCP/DinD). "
        "ROI is a first-year screening attempt, not a bid."
    )

    ws = workspace_root()
    reports = reports_dir()
    path = compare_path(reports)
    payload = load_compare(path, reports_dir=reports)
    if payload is None:
        payload = empty_compare_stub(measure_ids=list(DEFAULT_G36_ECMS))
        merge_full_parity_ss(payload, reports)
        write_compare(path, payload)

    # --- Run controls ---
    c1, c2, c3 = st.columns([2, 1, 1])
    twin_hint = payload.get("twin_run") or "(pick best G14 Twin)"
    c1.markdown(f"**Twin:** `{twin_hint}`")
    dry = c2.checkbox("Dry-run only", value=False, key="ecm_compare_dry")
    run = c3.button("Run EnergyPlus ECMs", type="primary", key="ecm_compare_run")

    if run:
        with st.spinner("Patching Twin IDF + EnergyPlus sims (MCP/DinD)…"):
            try:
                result = run_ecms_on_twin(
                    workspace=ws,
                    measure_ids=list(DEFAULT_G36_ECMS),
                    profile=profile or {},
                    dry_run=dry,
                    write_compare=True,
                )
                payload = result.get("compare") or payload
                merge_full_parity_ss(payload, reports)
                if result.get("ok"):
                    st.success(
                        f"Wrote `{result.get('compare_path')}` · twin=`{result.get('twin_run')}`"
                        + (" (dry-run)" if dry else "")
                    )
                else:
                    st.error("ECM run failed — see logs")
            except Exception as exc:
                st.error(f"EnergyPlus ECM run failed: {exc}")

    ss = payload.get("spreadsheet") or {}
    ep = payload.get("energyplus") or {}
    a, b = st.columns(2)
    with a:
        st.subheader("Spreadsheet calc")
        st.info(
            f"Status: **{ss.get('status', 'pending_external')}**  \n"
            f"{ss.get('note') or 'Drop external ESCO / full-parity compare JSON — columns stay blank until present.'}"
        )
    with b:
        st.subheader("EnergyPlus calc")
        st.info(
            f"Status: **{ep.get('status', 'empty')}** · source `{ep.get('source', '—')}`  \n"
            f"Weather: `{((ep.get('weather_suitability') or payload.get('energyplus') or {}).get('mode') if isinstance(ep.get('weather_suitability'), dict) else (payload.get('weather') or '—'))}`"
        )
        wsuit = payload.get("energyplus", {}).get("weather_suitability") or {}
        if isinstance(wsuit, dict) and wsuit.get("mode"):
            st.caption(f"{wsuit.get('mode')}: {wsuit.get('reason', '')}")

    st.subheader("Energy · cost · ROI")
    df = _compare_table(payload)
    if df.empty:
        st.warning("No measures yet — click **Run EnergyPlus ECMs**.")
    else:
        # Friendly display: blank spreadsheet cells as —
        show = df.copy()
        for col in show.columns:
            if col == "measure":
                continue
            show[col] = show[col].map(_fmt)
        st.dataframe(show, hide_index=True, width="stretch")

    # Required: monthly ±% fuel charts (E+ vs actual). Never collapse when JSON missing.
    twin_run = payload.get("twin_run") or twin_hint
    per_month: list[dict[str, Any]] = []
    try:
        from wattlab.studio.monthly_pct_off import load_per_month_from_run
        from wattlab.studio.workspace import runs_dir

        run_dir = None
        if twin_run and twin_run not in ("(pick best G14 Twin)",):
            cand = Path(str(twin_run))
            if cand.is_dir():
                run_dir = cand
            else:
                under = runs_dir() / str(twin_run)
                if under.is_dir():
                    run_dir = under
        if run_dir is None:
            # Best-effort: newest run with a scorecard
            from wattlab.studio.g14_history import iter_g14_history

            for row in iter_g14_history(runs_dir(), limit=8):
                d = row.get("dir")
                if d:
                    per_month = load_per_month_from_run(d)
                    if per_month:
                        twin_run = str(d)
                        break
        else:
            per_month = load_per_month_from_run(run_dir)
    except Exception as exc:
        st.caption(f"Monthly fuel load skipped: {exc}")

    from wattlab.studio.monthly_dial_chart import render_required_monthly_pct_charts

    render_required_monthly_pct_charts(
        per_month,
        key_prefix="ecm_monthly_pm",
        twin_hint=str(twin_run) if twin_run else None,
    )

    with st.expander("Honesty / contract", expanded=False):
        st.write(payload.get("honesty") or "")
        st.code(json.dumps({"path": str(path), "schema": payload.get("schema")}, indent=2))
        st.caption(
            "Spreadsheet ``ss_*`` fills from ``reports/ecm_full_parity_compare.json`` when present "
            "(BUG-ECM-015 / ENH-VIBE-002). EnergyPlus remains the Twin cascade path."
        )

    # Nested notebooks under reports/notebooks/** (full_parity_ecm/, packages, …)
    nb_dir = reports / "notebooks"
    leftovers = discover_notebook_xlsx(nb_dir)
    if leftovers:
        with st.expander("Legacy notebooks on disk (not the product path)", expanded=False):
            for p in leftovers:
                rel = p.relative_to(nb_dir) if p.is_relative_to(nb_dir) else Path(p.name)
                key = f"legacy_dl_{rel.as_posix().replace('/', '__')}"
                st.download_button(
                    f"Download {rel.as_posix()}",
                    data=p.read_bytes(),
                    file_name=p.name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=key,
                )
