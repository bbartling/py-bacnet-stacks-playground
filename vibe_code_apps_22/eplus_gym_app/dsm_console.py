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


def meter_peak_day_for_period(
    bas: pd.DataFrame,
    *,
    preset: str,
    peak_anchor: str,
    month: str | None = None,
) -> dict[str, Any]:
    """Pick the BAS meter peak day inside a period. Live E+ still runs that one day."""
    from eplus_gym_app.period_explorer import days_for_period

    if bas is None or bas.empty or "local_day" not in bas.columns:
        return {
            "day": peak_anchor,
            "preset": preset,
            "month": month,
            "window_days": [peak_anchor],
            "actual_peak_kw": None,
            "why": "no interval meter rows; using published dial peak day",
        }
    days = days_for_period(bas, preset=preset, peak_day=peak_anchor, month=month)
    window = bas.loc[bas["local_day"].astype(str).isin(set(days))]
    if window.empty or "kw_avg" not in window.columns:
        return {
            "day": peak_anchor,
            "preset": preset,
            "month": month,
            "window_days": list(days),
            "actual_peak_kw": None,
            "why": "period window empty; using published dial peak day",
        }
    idx = window["kw_avg"].idxmax()
    day = str(window.loc[idx, "local_day"])
    peak_kw = float(window.loc[idx, "kw_avg"])
    label = preset
    if preset == "Calendar month" and month:
        label = f"Calendar month {month}"
    return {
        "day": day,
        "preset": preset,
        "month": month,
        "window_days": list(days),
        "actual_peak_kw": peak_kw,
        "why": f"BAS meter peak inside {label} ({len(days)} day window)",
    }


def pick_run_day(bundle: SiteUiBundle, preset: str, month: str | None = None) -> str:
    return pick_run_context(bundle, preset, month)["day"]


def pick_run_context(
    bundle: SiteUiBundle, preset: str, month: str | None = None
) -> dict[str, Any]:
    """Resolve which single calendar day a Run will simulate."""
    peak = bundle.dial_ladder.peak_day
    try:
        from eplus_gym_app.load_profiles import load_bas_demand_oat

        bas = load_bas_demand_oat(bundle, csv_path=bundle.bas_demand_oat_csv)
    except Exception:  # noqa: BLE001
        bas = pd.DataFrame()
    ctx = meter_peak_day_for_period(
        bas, preset=preset, peak_anchor=peak, month=month
    )
    farm = resolve_w2a_farm_root(bundle.site)
    farm_days = list_farm_days(bundle.site, "baseline", farm_root=farm)
    ctx["farm_has_day"] = ctx["day"] in set(farm_days)
    ctx["bas"] = bas
    return ctx


def actual_day_profile(bundle: SiteUiBundle, day: str) -> pd.DataFrame:
    try:
        from eplus_gym_app.load_profiles import load_bas_demand_oat, peak_day_bas_profile

        bas = load_bas_demand_oat(bundle, csv_path=bundle.bas_demand_oat_csv)
        return peak_day_bas_profile(bas, str(day)[:10])
    except Exception:  # noqa: BLE001
        return pd.DataFrame()


def stage_idf_for_day(src: Path, dest: Path, day: str) -> Path:
    """Copy IDF with RunPeriod clipped to ``day``. Never overwrite the champion."""
    from datetime import date

    from eplus_native.idf_stage import patch_run_period

    src = Path(src)
    dest = Path(dest)
    if dest.resolve() == src.resolve():
        raise ValueError("refusing to overwrite source IDF; pass a staged dest path")
    d = date.fromisoformat(str(day)[:10])
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        patch_run_period(
            src.read_text(encoding="utf-8"),
            begin_month=d.month,
            begin_day=d.day,
            end_month=d.month,
            end_day=d.day,
            begin_year=d.year,
            end_year=d.year,
            name=f"DSM_{d.isoformat()}",
        ),
        encoding="utf-8",
    )
    return dest


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


def _resolve_epw(bundle: SiteUiBundle) -> Path | None:
    epw = bundle.epw
    if epw is not None and Path(epw).is_file():
        return Path(epw)
    weather = bundle.site / "eplus" / "weather"
    if not weather.is_dir():
        return None
    cands = sorted(weather.glob("madison_amy*.epw")) or sorted(weather.glob("*.epw"))
    return cands[0] if cands else None


def _eplus_with_oat_f(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "oat_c" in out.columns and "oat_f" not in out.columns:
        out["oat_f"] = out["oat_c"].astype(float) * 9.0 / 5.0 + 32.0
    return out


def _store_run(
    *,
    df: pd.DataFrame,
    actual: pd.DataFrame,
    kpis: dict[str, Any],
    strategy: str,
    day: str,
    preset: str,
    mode: str,
    epw_name: str,
    why: str,
    window_n: int,
) -> None:
    import streamlit as st

    st.session_state["dsm_last"] = {
        "kpis": kpis,
        "frame": df,
        "actual": actual,
        "title": f"E+ A04 {strategy} vs Actual meter · {day} · {preset}",
        "strategy": strategy,
        "day": day,
        "preset": preset,
        "mode": mode,
        "epw_name": epw_name,
        "why": why,
        "window_n": window_n,
    }


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

    from eplus_gym_app.plots import dsm_panel_figure, dsm_trajectory_figure

    st.subheader("Run DSM")
    st.caption(
        f"Champion `{bundle.dsm_champion}` · W2A_PHYSICAL_DSM · promote=False. "
        "Lookup if an A04 farm exists; otherwise live EnergyPlus via CLI subprocess."
    )
    mode, reason = resolve_dsm_mode(bundle.site)
    st.info(f"Mode: **{mode}** — {reason}")

    month_opts = [bundle.dial_ladder.peak_day[:7], "2026-01", "2026-02"]
    try:
        from eplus_gym_app.load_profiles import load_bas_demand_oat

        bas_months = load_bas_demand_oat(bundle, csv_path=bundle.bas_demand_oat_csv)
        month_opts.extend(str(d)[:7] for d in bas_months["local_day"].astype(str))
    except Exception:  # noqa: BLE001
        pass
    month_opts = sorted({m for m in month_opts if m and len(m) == 7})

    c1, c2, c3 = st.columns(3)
    with c1:
        strategy = st.selectbox("Strategy", list(DEPLOYABLE_STRATEGIES), key="dsm_strategy")
    with c2:
        preset = st.select_slider(
            "Period", options=list(PERIOD_PRESETS), value="Peak day", key="dsm_period"
        )
    with c3:
        month = st.selectbox(
            "Month", options=month_opts, key="dsm_month", disabled=preset != "Calendar month"
        )

    ctx = pick_run_context(bundle, preset, month if preset == "Calendar month" else None)
    day = ctx["day"]
    epw = _resolve_epw(bundle)
    epw_name = epw.name if epw is not None else "(no EPW)"
    window_n = len(ctx.get("window_days") or [])
    st.markdown(
        f"**Will simulate one day:** `{day}` — {ctx['why']}. "
        "Live E+ is **96 × 15-min steps**, not a full month/week run."
    )
    if ctx.get("actual_peak_kw") is not None:
        st.caption(
            f"That calendar date is the BAS meter peak in this window "
            f"({ctx['actual_peak_kw']:.0f} kW hourly). "
            f"E+ weather is **{epw_name}** (typical-year EPW on that date), "
            "not the observed Open-Meteo/BAS outdoor temperature for the real peak event."
        )

    if st.button("Run", key="dsm_run_btn", type="primary"):
        actual_peak = ctx.get("actual_peak_kw")
        if actual_peak is None:
            actual_peak = _actual_peak(bundle, day)
        actual = actual_day_profile(bundle, day)
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
                _store_run(
                    df=pack["frame"],
                    actual=actual,
                    kpis=pack["kpis"],
                    strategy=strategy,
                    day=day,
                    preset=preset,
                    mode="lookup",
                    epw_name=epw_name,
                    why=str(ctx["why"]),
                    window_n=window_n,
                )
            except FileNotFoundError as exc:
                st.error(str(exc))
                return
        else:
            champ = bundle.champion()
            idf = (champ.idf_path if champ else None) or bundle.idf_path
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
            _store_run(
                df=df,
                actual=actual,
                kpis=dsm_kpis(df, meta, actual_peak_kw=actual_peak),
                strategy=strategy,
                day=day,
                preset=preset,
                mode="live",
                epw_name=epw_name,
                why=str(ctx["why"]),
                window_n=window_n,
            )

    last = st.session_state.get("dsm_last")
    if not last:
        return
    stale = last.get("day") != day or last.get("preset") != preset or last.get("strategy") != strategy
    if stale:
        st.warning(
            f"Chart below is the **last Run** (`{last.get('preset')}` · `{last.get('day')}` · "
            f"`{last.get('strategy')}`). Click **Run** to simulate `{preset}` → `{day}`."
        )
    kpis = last["kpis"]
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("E+ peak kW", f"{kpis['peak_kw']:.0f}" if kpis.get("peak_kw") is not None else "—")
    k2.metric("E+ kWh", f"{kpis['kwh']:.0f}" if kpis.get("kwh") is not None else "—")
    k3.metric(
        "E+ vs Actual peak",
        f"{kpis['vs_actual_pct']:+.1f}%" if kpis.get("vs_actual_pct") is not None else "—",
    )
    k4.metric(
        "vs baseline",
        f"{kpis['vs_baseline_pct']:+.1f}%" if kpis.get("vs_baseline_pct") is not None else "—",
    )
    k5.metric("promote", "False")
    actual = last.get("actual")
    eplus = _eplus_with_oat_f(last["frame"])
    actual_peak_show = None
    if actual is not None and not getattr(actual, "empty", True) and "kw_avg" in actual.columns:
        actual_peak_show = float(actual["kw_avg"].max())
    eplus_oat = "—"
    if "oat_f" in eplus.columns and eplus["oat_f"].notna().any():
        eplus_oat = f"{float(eplus['oat_f'].min()):.0f}–{float(eplus['oat_f'].max()):.0f}°F"
    actual_oat = "—"
    if (
        actual is not None
        and not getattr(actual, "empty", True)
        and "oat_f" in actual.columns
        and actual["oat_f"].notna().any()
    ):
        actual_oat = f"{float(actual['oat_f'].min()):.0f}–{float(actual['oat_f'].max()):.0f}°F"
    actual_bit = (
        f" (peak {actual_peak_show:.0f} kW, OAT {actual_oat})"
        if actual_peak_show is not None
        else ""
    )
    st.info(
        f"**Last run** `{last.get('preset')}` · **{last.get('day')}** · `{last.get('strategy')}` · "
        f"{last.get('why')}. Black = **Actual BAS meter**{actual_bit}. "
        f"Teal = **EnergyPlus A04** (`{kpis.get('provenance')}`, OAT {eplus_oat} from **{last.get('epw_name')}**). "
        "Same calendar date; weather is **not** the observed peak-day OAT unless the EPW happens to match."
    )
    left, right = st.columns(2)
    with left:
        st.plotly_chart(
            dsm_panel_figure(
                actual if actual is not None else pd.DataFrame(),
                title=f"Actual BAS meter · {last.get('day')}",
                ycol="kw_avg",
                name="Actual (BAS meter)",
                color="#1f2a30",
                oat_col="oat_f",
                oat_name="Actual OAT °F",
            ),
            width="stretch",
            key=f"dsm_actual_{last.get('day')}_{last.get('preset')}",
        )
    with right:
        st.plotly_chart(
            dsm_panel_figure(
                eplus,
                title=f"EnergyPlus A04 {last.get('strategy')} · {last.get('day')}",
                ycol="facility_kw",
                name="E+ A04 facility kW",
                color="#2a9d8f",
                oat_col="oat_f",
                oat_name="E+ EPW OAT °F",
            ),
            width="stretch",
            key=f"dsm_eplus_{last.get('day')}_{last.get('strategy')}_{last.get('mode')}",
        )
    st.plotly_chart(
        dsm_trajectory_figure(
            eplus,
            actual=actual,
            title=last.get("title") or "E+ vs Actual",
        ),
        width="stretch",
        key=f"dsm_overlay_{last.get('day')}_{last.get('strategy')}_{last.get('preset')}_{last.get('mode')}",
    )
