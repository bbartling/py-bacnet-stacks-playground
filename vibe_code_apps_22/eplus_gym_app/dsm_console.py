"""BOPTEST-shaped DSM Run panel (W2A champion only)."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from eplus_gym.discover import energyplus_available
from eplus_gym.lookup_emulator import list_farm_days, resolve_w2a_farm_root, w2a_farm_ready
from eplus_gym.month_calendar import DEPLOYABLE_STRATEGIES
from eplus_gym.simulate import FAMILY_W2A, run_rule_episode, trajectory_frame
from eplus_gym_app.period_explorer import PERIOD_PRESETS

if TYPE_CHECKING:
    from eplus_gym_app.site_bundle import SiteUiBundle

_APP = Path(__file__).resolve().parents[1]
_CLI = _APP / "scripts" / "run_eplus_gym_rules.py"


def resolve_dsm_mode(site: Path, *, family: str = FAMILY_W2A) -> tuple[str, str]:
    """Return (lookup|live|error, reason). Never silently uses IdealLoads farm."""
    site = Path(site)
    if family != FAMILY_W2A:
        return "error", "human DSM console is W2A-only"
    if w2a_farm_ready(site):
        return "lookup", "A04 farm present under eplus/dsm_farm_w2a"
    if energyplus_available():
        return "live", "no A04 farm; live EnergyPlus via CLI subprocess"
    return (
        "error",
        "No A04 farm (eplus/dsm_farm_w2a) and EnergyPlus is unavailable. "
        "Will not fall back to IdealLoads. Agent: grow a sparse W2A farm or set ENERGYPLUS_ROOT.",
    )


def dsm_kpis(
    df: pd.DataFrame,
    meta: dict[str, Any],
    *,
    actual_peak_kw: float | None = None,
    baseline_peak_kw: float | None = None,
) -> dict[str, Any]:
    peak = float(df["facility_kw"].max()) if df is not None and not df.empty and "facility_kw" in df.columns else None
    kwh = (
        float(df["facility_kw"].sum() * 0.25)
        if df is not None and not df.empty and "facility_kw" in df.columns
        else None
    )
    vs_actual = None
    if peak is not None and actual_peak_kw not in (None, 0):
        vs_actual = (peak - float(actual_peak_kw)) / float(actual_peak_kw) * 100.0
    vs_base = None
    if peak is not None and baseline_peak_kw not in (None, 0):
        vs_base = (peak - float(baseline_peak_kw)) / float(baseline_peak_kw) * 100.0
    return {
        "peak_kw": peak,
        "kwh": kwh,
        "vs_actual_pct": vs_actual,
        "vs_baseline_pct": vs_base,
        "honesty": meta.get("honesty"),
        "provenance": meta.get("provenance"),
        "mode": meta.get("mode"),
        "family": meta.get("family"),
        "promote": bool(meta.get("promote", False)),
        "day": meta.get("day"),
        "strategy_id": meta.get("strategy_id"),
    }


def run_dsm_lookup(
    *,
    site_root: Path,
    strategy_id: str,
    day: str,
    actual_peak_kw: float | None = None,
) -> dict[str, Any]:
    result = run_rule_episode(
        site_root=Path(site_root),
        strategy_id=strategy_id,
        day=day,
        mode="lookup",
        family=FAMILY_W2A,
    )
    df = trajectory_frame(result)
    baseline_peak = None
    if strategy_id != "baseline":
        try:
            base = run_rule_episode(
                site_root=Path(site_root),
                strategy_id="baseline",
                day=day,
                mode="lookup",
                family=FAMILY_W2A,
            )
            bdf = trajectory_frame(base)
            if not bdf.empty and "facility_kw" in bdf.columns:
                baseline_peak = float(bdf["facility_kw"].max())
        except FileNotFoundError:
            baseline_peak = None
    kpis = dsm_kpis(
        df,
        result["meta"],
        actual_peak_kw=actual_peak_kw,
        baseline_peak_kw=baseline_peak,
    )
    return {"frame": df, "meta": result["meta"], "kpis": kpis}


def pick_run_day(bundle: SiteUiBundle, preset: str, month: str | None = None) -> str:
    peak = bundle.dial_ladder.peak_day
    farm = resolve_w2a_farm_root(bundle.site)
    days = list_farm_days(bundle.site, "baseline", farm_root=farm)
    if preset == "Calendar month" and month:
        month_days = [d for d in days if d.startswith(month)]
        if month_days:
            return month_days[-1]
    if peak in days:
        return peak
    if days:
        return days[-1]
    return peak


def start_live_subprocess(
    *,
    site: Path,
    strategy_id: str,
    day: str,
    epw: Path,
    idf: Path,
    out_dir: Path,
) -> subprocess.Popen:
    """Launch CLI live W2A run (do not bind pyenergyplus into Streamlit)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-u",
        str(_CLI),
        "--mode",
        "live",
        "--family",
        "w2a",
        "--strategies",
        strategy_id,
        "--day",
        day,
        "--epw",
        str(epw),
        "--idf",
        str(idf),
        "--out",
        str(out_dir),
    ]
    log = out_dir / "live.log"
    handle = log.open("w", encoding="utf-8")
    return subprocess.Popen(
        cmd,
        cwd=str(_APP),
        stdout=handle,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _actual_peak(bundle: SiteUiBundle, day: str) -> float | None:
    try:
        from eplus_gym_app.load_profiles import load_bas_demand_oat

        bas = load_bas_demand_oat(bundle, csv_path=bundle.bas_demand_oat_csv)
        sub = bas.loc[bas["local_day"].astype(str) == str(day)[:10]]
        if sub.empty:
            return None
        return float(sub["kw_avg"].max())
    except Exception:  # noqa: BLE001
        return None


def render_run_dsm_tab(bundle: SiteUiBundle) -> None:
    import streamlit as st

    from eplus_gym_app.plots import dsm_trajectory_figure

    st.subheader("Run DSM")
    st.caption(
        f"Champion `{bundle.dsm_champion}` · W2A_PHYSICAL_DSM · promote=False. "
        "Lookup if an A04 farm exists; otherwise live EnergyPlus via CLI subprocess."
    )
    mode, reason = resolve_dsm_mode(bundle.site)
    st.info(f"Mode: **{mode}** — {reason}")

    c1, c2, c3 = st.columns(3)
    with c1:
        strategy = st.selectbox(
            "Strategy",
            list(DEPLOYABLE_STRATEGIES),
            key="dsm_strategy",
        )
    with c2:
        preset = st.select_slider(
            "Period",
            options=list(PERIOD_PRESETS),
            value="Peak day",
            key="dsm_period",
        )
    with c3:
        month = st.selectbox(
            "Month",
            options=sorted(
                {
                    bundle.dial_ladder.peak_day[:7],
                    "2026-01",
                    "2026-02",
                }
            ),
            key="dsm_month",
            disabled=preset != "Calendar month",
        )

    day = pick_run_day(bundle, preset, month if preset == "Calendar month" else None)
    st.caption(f"Run day `{day}` (96 × 15-min steps)")

    if st.button("Run", key="dsm_run_btn", type="primary"):
        actual_peak = _actual_peak(bundle, day)
        if mode == "error":
            st.error(reason)
            return
        if mode == "lookup":
            try:
                pack = run_dsm_lookup(
                    site_root=bundle.site,
                    strategy_id=strategy,
                    day=day,
                    actual_peak_kw=actual_peak,
                )
                st.session_state["dsm_last"] = {
                    "kpis": pack["kpis"],
                    "frame": pack["frame"],
                    "title": f"{strategy} · {day} · lookup",
                }
            except FileNotFoundError as exc:
                st.error(str(exc))
                return
        else:
            champ = bundle.champion()
            idf = (champ.idf_path if champ else None) or bundle.idf_path
            epw = bundle.epw
            if idf is None or not Path(idf).is_file():
                st.error("No champion IDF on the published pack.")
                return
            if epw is None or not Path(epw).is_file():
                st.error("No EPW on the published pack (bundle.epw). Agent must publish weather.")
                return
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            out_dir = bundle.site / "reports" / "eplus_gym" / "runs" / f"{stamp}_{strategy}"
            with st.status("Live EnergyPlus (subprocess)…", expanded=True) as status:
                proc = start_live_subprocess(
                    site=bundle.site,
                    strategy_id=strategy,
                    day=day,
                    epw=Path(epw),
                    idf=Path(idf),
                    out_dir=out_dir,
                )
                code = proc.wait()
                log = out_dir / "live.log"
                tail = ""
                if log.is_file():
                    tail = "\n".join(log.read_text(encoding="utf-8", errors="ignore").splitlines()[-20:])
                    st.code(tail or "(empty log)")
                if code != 0:
                    status.update(label="Live run failed", state="error")
                    st.error(f"CLI exited {code}")
                    return
                status.update(label="Live run finished", state="complete")
            # Prefer trajectory parquet written by CLI
            frames = sorted(out_dir.glob("traj_*.parquet"))
            if not frames:
                frames = sorted((out_dir / "runs").glob("*.parquet")) if (out_dir / "runs").is_dir() else []
            if not frames:
                st.warning(f"Live finished but no trajectory parquet under {out_dir}")
                return
            df = pd.read_parquet(frames[0])
            meta = {
                "honesty": "W2A_PHYSICAL_DSM",
                "provenance": "ENERGYPLUS_PYTHON_API",
                "mode": "live",
                "family": "w2a",
                "promote": False,
                "day": day,
                "strategy_id": strategy,
            }
            card = out_dir / "rule_dr_scorecard.json"
            if card.is_file():
                try:
                    doc = json.loads(card.read_text(encoding="utf-8"))
                    rows = doc.get("strategies") or []
                    if rows:
                        meta["honesty"] = rows[0].get("honesty") or meta["honesty"]
                        meta["provenance"] = rows[0].get("provenance") or meta["provenance"]
                except (OSError, json.JSONDecodeError):
                    pass
            st.session_state["dsm_last"] = {
                "kpis": dsm_kpis(df, meta, actual_peak_kw=actual_peak),
                "frame": df,
                "title": f"{strategy} · {day} · live",
            }

    last = st.session_state.get("dsm_last")
    if not last:
        return
    kpis = last["kpis"]
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Peak kW", f"{kpis['peak_kw']:.0f}" if kpis.get("peak_kw") is not None else "—")
    k2.metric("kWh", f"{kpis['kwh']:.0f}" if kpis.get("kwh") is not None else "—")
    k3.metric(
        "vs Actual",
        f"{kpis['vs_actual_pct']:+.1f}%" if kpis.get("vs_actual_pct") is not None else "—",
    )
    k4.metric(
        "vs baseline",
        f"{kpis['vs_baseline_pct']:+.1f}%" if kpis.get("vs_baseline_pct") is not None else "—",
    )
    k5.metric("promote", "False")
    st.caption(
        f"honesty=`{kpis.get('honesty')}` · provenance=`{kpis.get('provenance')}` · "
        f"mode=`{kpis.get('mode')}` · day=`{kpis.get('day')}`"
    )
    st.plotly_chart(
        dsm_trajectory_figure(last["frame"], title=last.get("title") or "DSM run"),
        width="stretch",
    )
