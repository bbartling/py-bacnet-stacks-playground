"""Optimize Tomorrow — EnergyPlus DSM screening UI (proposal only)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from eplus_gym.tariff_contract import latex_cost_equations

_APP = Path(__file__).resolve().parents[1]
_STUDY_CLI = _APP / "scripts" / "run_dsm_optimization_study.py"

SCREENING = "ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY"


def _opt_root(site: Path) -> Path:
    return Path(site) / "reports" / "eplus_gym" / "optimization"


def list_studies(site: Path) -> list[Path]:
    root = _opt_root(site)
    if not root.is_dir():
        return []
    return sorted([p for p in root.iterdir() if p.is_dir()], reverse=True)


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) else None
    except Exception:  # noqa: BLE001
        return None


def render_cost_equations() -> None:
    """Billing-floor cost reduction math (KaTeX via st.latex)."""
    eq = latex_cost_equations()
    st.subheader("Cost reduction objective")
    st.caption(
        f"{SCREENING}. Default money mode is **PHYSICAL_ONLY** — "
        "illustrative dollars never select an operational winner."
    )
    st.markdown("**Total screening cost** (energy + incremental demand only):")
    st.latex(eq["total"])
    st.markdown("**Energy cost** over 96 quarter-hour intervals:")
    st.latex(eq["energy"])
    st.markdown(
        "**Billing-floor demand** — charge only kW above the month-to-date peak "
        r"$P^{\mathrm{MTD}}$, never a full monthly demand alone:"
    )
    st.latex(eq["demand"])
    st.markdown("**Cost reduction vs baseline controls:**")
    st.latex(eq["savings"])
    st.latex(eq["physical_only"])
    st.markdown(
        r"Comfort is a **hard gate** on the six BAS zone aggregates "
        r"($T_{\mathrm{zone}} \in [T_{\min}, T_{\max}]$ occupied/unoccupied). "
        r"Infeasible candidates cannot win."
    )


def render_optimize_tomorrow_tab(bundle) -> None:
    site = Path(bundle.site)
    st.header("Optimize Tomorrow")
    st.info(SCREENING)
    st.caption(
        "Retrospective AMY replay / perfect-forecast screening. "
        "Approve writes `approved_recommendation.json` only — "
        "never Site Config, never BACnet."
    )

    render_cost_equations()

    st.divider()
    c1, c2, c3 = st.columns(3)
    with c1:
        day = st.text_input("Target day (ISO)", value="2026-01-26", key="opt_day")
    with c2:
        budget = st.number_input("Candidate budget", min_value=2, max_value=40, value=6)
    with c3:
        money = st.selectbox(
            "Money mode",
            ["PHYSICAL_ONLY", "ILLUSTRATIVE", "VERIFIED_TARIFF"],
            index=0,
            help="PHYSICAL_ONLY ranks energy/peak/comfort — $ cannot pick a winner.",
        )

    if st.button("Launch optimization study", type="primary", key="opt_launch"):
        cmd = [
            sys.executable,
            str(_STUDY_CLI),
            "--site-root",
            str(site),
            "--day",
            day,
            "--budget",
            str(int(budget)),
            "--money-mode",
            money,
        ]
        log_dir = _opt_root(site) / "_supervisor"
        log_dir.mkdir(parents=True, exist_ok=True)
        log = log_dir / "last_launch.log"
        try:
            with log.open("w", encoding="utf-8") as fh:
                proc = subprocess.Popen(
                    cmd,
                    cwd=str(_APP),
                    stdout=fh,
                    stderr=subprocess.STDOUT,
                    env={**dict(**{k: v for k, v in __import__("os").environ.items()}), "SITE_ROOT": str(site)},
                )
            st.success(f"Started PID {proc.pid}. Log: `{log}`")
            st.caption("Refresh to load new study folders under reports/eplus_gym/optimization/.")
        except Exception as exc:  # noqa: BLE001
            st.error(f"Failed to launch study: {exc}")

    studies = list_studies(site)
    if not studies:
        st.warning("No optimization studies yet.")
        return

    labels = [p.name for p in studies]
    pick = st.selectbox("Study", labels, index=0, key="opt_study_pick")
    root = _opt_root(site) / pick
    req = _load_json(root / "study_request.json")
    rec = _load_json(root / "recommendation.json")
    pareto = _load_json(root / "pareto_frontier.json")
    hashes = _load_json(root / "hashes.json")

    if req:
        st.caption(
            f"Forecast: `{req.get('forecast_kind')}` · money `{req.get('money_mode')}` · "
            f"day `{req.get('day')}`"
        )
    if hashes:
        st.caption(f"Champion sha256 `{hashes.get('champion_sha256', '')[:12]}…` (must stay unchanged)")

    jl = root / "candidates.jsonl"
    rows: list[dict] = []
    if jl.is_file():
        for line in jl.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    if rows:
        st.subheader("Candidates")
        show = pd.DataFrame(rows)
        cols = [
            c
            for c in (
                "candidate_hash",
                "status",
                "daily_kwh",
                "peak_kw",
                "comfort_degree_hours",
                "feasible",
                "total_incremental_cost",
                "money_mode",
            )
            if c in show.columns
        ]
        st.dataframe(show[cols] if cols else show, use_container_width=True)

    if pareto and pareto.get("frontier"):
        st.subheader("Pareto frontier")
        st.dataframe(pd.DataFrame(pareto["frontier"]), use_container_width=True)

    if rec:
        st.subheader("Recommendation (proposal only)")
        st.json(rec.get("recommended") or {"note": "no feasible winner"})
        approved_path = root / "approved_recommendation.json"
        if st.button("Approve recommendation", key="opt_approve"):
            approved = {
                **rec,
                "approved": True,
                "approved_note": (
                    "Human approved proposal artifact only — "
                    "Site Config / BACnet NOT modified."
                ),
            }
            approved_path.write_text(json.dumps(approved, indent=2) + "\n", encoding="utf-8")
            st.success(f"Wrote `{approved_path}` (no Site Config / BACnet write).")
        if approved_path.is_file():
            st.caption(f"Already approved: `{approved_path}`")

    # Overlay first successful trajectory if present
    for r in rows:
        if r.get("status") == "ok" and r.get("trajectory"):
            pq = Path(r["trajectory"])
            if pq.is_file():
                try:
                    df = pd.read_parquet(pq)
                    st.subheader("Sample trajectory overlay")
                    if "facility_kw" in df.columns:
                        st.line_chart(df.set_index("step")[["facility_kw"]])
                    zone_cols = [c for c in df.columns if c.startswith("zone_temp_")]
                    if zone_cols:
                        st.caption("BAS six-zone comfort aggregates (°F)")
                        st.line_chart(df.set_index("step")[zone_cols])
                except Exception as exc:  # noqa: BLE001
                    st.caption(f"Trajectory plot skipped: {exc}")
            break
