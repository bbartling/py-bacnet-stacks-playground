"""G14 calibration history across published Twin runs (epoch / loss-style chart).

Iteration index is **per-building dial history** (e.g. ``geo_b100_*``), not a
global mtime soup mixing B50 and B100. Operators must never read “Iteration N”
as campus-wide training epoch without a building filter.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from wattlab.studio.eui_charts import plotly_layout_clean
from wattlab.studio.ep_viz import list_iteration_runs, read_run_progress

G14_NMBE_GATE = 5.0
G14_CVRMSE_GATE = 15.0

# Default scan window when filtering by building family (many B50 dials exist).
DEFAULT_G14_HISTORY_LIMIT = 80
# When scanning for family discovery / “all matching prefix”, allow a wide window.
G14_HISTORY_SCAN_MAX = 500

_BUILDING_FAMILY_RE = re.compile(r"^(geo_b\d+)", re.IGNORECASE)
_SHORT_STEM_RE = re.compile(r"(?:^|_)(r\d+|i\d+)(?:_|$)", re.IGNORECASE)


def building_family_from_run_id(run_id: str | None) -> str | None:
    """Extract building dial family from a run id.

    Examples::
        geo_b100_6stack_shape_r56_sched_mild → geo_b100
        geo_b50_i32_freecool_julHW → geo_b50
    """
    if not run_id:
        return None
    rid = str(run_id).strip()
    m = _BUILDING_FAMILY_RE.match(rid)
    if m:
        return m.group(1).lower()
    parts = rid.split("_")
    if len(parts) >= 2 and parts[0].lower() == "geo" and parts[1].lower().startswith("b"):
        return f"{parts[0]}_{parts[1]}".lower()
    return None


def run_id_short_stem(run_id: str | None) -> str:
    """Short dial stem for axis ticks (``r56``, ``i32``); else truncated run_id."""
    if not run_id:
        return "?"
    rid = str(run_id)
    m = _SHORT_STEM_RE.search(rid)
    if m:
        return m.group(1).lower()
    fam = building_family_from_run_id(rid)
    if fam and rid.lower().startswith(fam):
        rest = rid[len(fam) :].lstrip("_")
        return (rest[:16] if rest else fam) or rid[-12:]
    return rid[-12:]


def discover_building_families(runs_root: Path | str, *, limit: int = G14_HISTORY_SCAN_MAX) -> list[str]:
    """Sorted unique ``geo_bNN`` families present under ``runs/``.

    Directory-name scan only (no scorecard / eplusout I/O).
    """
    root = Path(runs_root)
    if not root.is_dir():
        return []
    found: set[str] = set()
    n = 0
    try:
        dirs = sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return []
    for d in dirs:
        if not d.is_dir() or d.name.startswith("_"):
            continue
        fam = building_family_from_run_id(d.name)
        if fam:
            found.add(fam)
        n += 1
        if n >= limit:
            break
    return sorted(found)


def filter_rows_by_building_family(
    rows: list[dict[str, Any]],
    family: str | None,
) -> list[dict[str, Any]]:
    """Keep rows whose run_id matches ``family`` (e.g. ``geo_b100``).

    ``family`` None / empty / ``all`` → no filter (mixed campus — avoid for charts).
    """
    if not family or str(family).strip().lower() in {"all", "*", "(all)"}:
        return list(rows)
    want = str(family).strip().lower()
    out: list[dict[str, Any]] = []
    for r in rows:
        rid = r.get("run_id") or (Path(str(r["dir"])).name if r.get("dir") else None)
        fam = building_family_from_run_id(str(rid) if rid else None)
        if fam == want:
            out.append(r)
    return out


def _normalize_building_family(family: str | None) -> str | None:
    """Return a concrete family prefix, or None for no filter (incl. all sentinels)."""
    if not family:
        return None
    s = str(family).strip()
    if not s or s.lower() in {"all", "*", "(all)"}:
        return None
    return s


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError, TypeError):
        return {}


def _g14_from_scorecard(data: dict[str, Any]) -> dict[str, Any]:
    """Extract NMBE/CVRMSE from calibration_scorecard or wattlab_report utility_bills."""
    bills = data.get("utility_bills") or {}
    if not isinstance(bills, dict):
        bills = {}
    stats_e = bills.get("stats_electricity") or bills.get("stats") or {}
    stats_g = bills.get("stats_natural_gas") or bills.get("stats_gas") or {}
    if not isinstance(stats_e, dict):
        stats_e = {}
    if not isinstance(stats_g, dict):
        stats_g = {}
    out = {
        "nmbe_elec_pct": stats_e.get("nmbe_pct", data.get("nmbe_elec_pct")),
        "cvrmse_elec_pct": stats_e.get("cvrmse_pct", data.get("cvrmse_elec_pct")),
        "nmbe_gas_pct": stats_g.get("nmbe_pct", data.get("nmbe_gas_pct")),
        "cvrmse_gas_pct": stats_g.get("cvrmse_pct", data.get("cvrmse_gas_pct")),
        "pass_fail": bills.get("pass_fail")
        or data.get("pass_fail")
        or data.get("status")
        or data.get("overall"),
    }
    return out


def extract_run_g14(run_dir: Path | str | None) -> dict[str, Any]:
    """Load G14 metrics from a published run directory."""
    if not run_dir:
        return {}
    root = Path(run_dir)
    for name in ("calibration_scorecard.json", "campaign_stamp.json", "wattlab_report.json"):
        p = root / name
        if p.is_file():
            g = _g14_from_scorecard(_load_json(p))
            if any(g.get(k) is not None for k in ("nmbe_elec_pct", "cvrmse_elec_pct", "nmbe_gas_pct")):
                return g
    return {}


def iter_g14_history(
    runs_root: Path | str,
    *,
    limit: int = DEFAULT_G14_HISTORY_LIMIT,
    building_family: str | None = None,
    prefix: str | None = None,
) -> list[dict[str, Any]]:
    """Return chronological G14 rows for published runs (oldest → newest).

    When ``building_family`` or ``prefix`` is set (e.g. ``geo_b100``), only matching
    run ids are kept and iteration renumbering is per-family dial history.
    """
    fam = _normalize_building_family(building_family or prefix)
    # Scan widely when filtering so older B100 runs are not crowded out by B50 dials.
    scan_limit = max(limit, G14_HISTORY_SCAN_MAX) if fam else limit
    rows: list[dict[str, Any]] = []
    for h in list_iteration_runs(Path(runs_root), limit=scan_limit, prefix=fam):
        d = Path(str(h["dir"])) if h.get("dir") else None
        rid = h.get("run_id") or (d.name if d else None)
        g14 = extract_run_g14(d)
        prog = read_run_progress(d) if d else {}
        rows.append(
            {
                "run_id": rid,
                "building_family": building_family_from_run_id(str(rid) if rid else None),
                "short_stem": run_id_short_stem(str(rid) if rid else None),
                "dir": str(d) if d else None,
                "started_at": h.get("started_at") or prog.get("started_at"),
                "finished_at": h.get("finished_at") or prog.get("finished_at"),
                "status": h.get("status"),
                "hypothesis": h.get("hypothesis"),
                "has_eplusout": h.get("has_eplusout"),
                "elapsed_s": h.get("elapsed_s"),
                "mtime": h.get("mtime"),
                **g14,
            }
        )

    if fam:
        rows = filter_rows_by_building_family(rows, fam)

    def _sort_key(r: dict[str, Any]) -> tuple:
        ts = r.get("started_at") or ""
        if ts:
            return (0, str(ts), str(r.get("run_id") or ""))
        mt = r.get("mtime")
        return (1, float(mt) if mt is not None else 0.0, str(r.get("run_id") or ""))

    rows.sort(key=_sort_key)
    # Cap after filter+sort so chart stays readable
    if len(rows) > limit:
        rows = rows[-limit:]
    return rows


def assign_run_numbers(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add chronological ``run`` 1…N (oldest → newest) within the filtered set."""
    out: list[dict[str, Any]] = []
    for i, r in enumerate(rows, start=1):
        out.append({**r, "run": i})
    return out


def _g14_error_score(row: dict[str, Any]) -> float:
    """Lower is better: |NMBE|+CVRMSE elec (+ gas when present)."""
    total = 0.0
    n = 0
    for nk, ck in (
        ("nmbe_elec_pct", "cvrmse_elec_pct"),
        ("nmbe_gas_pct", "cvrmse_gas_pct"),
    ):
        try:
            nmbe = row.get(nk)
            cv = row.get(ck)
            if nmbe is None and cv is None:
                continue
            part = 0.0
            if nmbe is not None:
                part += abs(float(nmbe))
            if cv is not None:
                part += abs(float(cv))
            total += part
            n += 1
        except (TypeError, ValueError):
            continue
    if n == 0:
        return float("inf")
    return total


def _is_g14_pass(row: dict[str, Any]) -> bool:
    pf = str(row.get("pass_fail") or "").strip().upper()
    return pf in {"PASS", "PASSED", "OK", "SUCCESS"}


def pick_best_g14_run(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Choose best published Twin run for ECM baseline **within the given rows**.

    Callers must pass building-filtered rows; this never mixes B50 with B100.
    Prefer G14 PASS; else minimize |NMBE|+CVRMSE (elec, plus gas when present).
    """
    if not rows:
        return None
    numbered = rows if all("run" in r for r in rows) else assign_run_numbers(list(rows))
    with_metrics = [
        r
        for r in numbered
        if r.get("nmbe_elec_pct") is not None
        or r.get("cvrmse_elec_pct") is not None
        or r.get("nmbe_gas_pct") is not None
    ]
    pool = with_metrics or numbered
    passes = [r for r in pool if _is_g14_pass(r)]
    candidates = passes if passes else pool
    return min(candidates, key=_g14_error_score)


def g14_epoch_figure(
    rows: list[dict[str, Any]],
    *,
    height: int = 440,
    building_family: str | None = None,
):
    """Plot |NMBE| and CV(RMSE) vs per-building iteration index.

    X-axis ticks use short stems (``r56``, ``i32``); hover shows full ``run_id``
    and building family. G14 PASS points get star markers + annotation.
    """
    import plotly.graph_objects as go

    usable = [
        r
        for r in rows
        if r.get("nmbe_elec_pct") is not None or r.get("cvrmse_elec_pct") is not None
    ]
    fam_label = building_family or (
        usable[0].get("building_family") if usable else None
    )
    title_suffix = f" · {fam_label}" if fam_label else ""
    fig = go.Figure()
    if not usable:
        fig.add_annotation(
            text=(
                "No per-run G14 scorecards for this building filter — "
                "publish calibration_scorecard.json with each Twin run."
            ),
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
        )
        return plotly_layout_clean(
            fig,
            title=f"G14 calibration across iterations{title_suffix}",
            height=height,
            yaxis_title="% error",
        )

    numbered = usable if all("run" in r for r in usable) else assign_run_numbers(list(usable))
    # Same pool as caption / pick_best: only rows with elec metrics (usable).
    best = pick_best_g14_run(numbered)
    xs = [int(r.get("run") or i) for i, r in enumerate(numbered, start=1)]
    ticktext = [str(r.get("short_stem") or run_id_short_stem(r.get("run_id"))) for r in numbered]
    hover = []
    for r in numbered:
        rid = r.get("run_id") or "?"
        bf = r.get("building_family") or building_family_from_run_id(str(rid)) or "?"
        g14 = str(r.get("pass_fail") or "—")
        hover.append(
            f"<b>{rid}</b><br>building={bf}<br>G14={g14}<br>"
            f"{r.get('started_at') or ''}<br>{(r.get('hypothesis') or '')[:80]}"
        )

    def _abs_series(key: str) -> list[float | None]:
        out: list[float | None] = []
        for r in numbered:
            v = r.get(key)
            try:
                out.append(abs(float(v)) if v is not None else None)
            except (TypeError, ValueError):
                out.append(None)
        return out

    fig.add_scatter(
        x=xs,
        y=_abs_series("nmbe_elec_pct"),
        mode="lines+markers",
        name="|NMBE| elec %",
        text=hover,
        customdata=[r.get("run_id") for r in numbered],
        hovertemplate="%{text}<br>iter %{x}<br>|NMBE| %{y:.2f}%<extra></extra>",
        line=dict(color="#1f77b4", width=2),
    )
    fig.add_scatter(
        x=xs,
        y=_abs_series("cvrmse_elec_pct"),
        mode="lines+markers",
        name="CV(RMSE) elec %",
        text=hover,
        customdata=[r.get("run_id") for r in numbered],
        hovertemplate="%{text}<br>iter %{x}<br>CVRMSE %{y:.2f}%<extra></extra>",
        line=dict(color="#ff7f0e", width=2),
    )
    if any(r.get("nmbe_gas_pct") is not None for r in numbered):
        fig.add_scatter(
            x=xs,
            y=_abs_series("nmbe_gas_pct"),
            mode="lines+markers",
            name="|NMBE| gas %",
            text=hover,
            hovertemplate="%{text}<br>iter %{x}<br>|NMBE| gas %{y:.2f}%<extra></extra>",
            line=dict(color="#2ca02c", width=2, dash="dot"),
        )
    if any(r.get("cvrmse_gas_pct") is not None for r in numbered):
        fig.add_scatter(
            x=xs,
            y=_abs_series("cvrmse_gas_pct"),
            mode="lines+markers",
            name="CV(RMSE) gas %",
            text=hover,
            hovertemplate="%{text}<br>iter %{x}<br>CVRMSE gas %{y:.2f}%<extra></extra>",
            line=dict(color="#9467bd", width=2, dash="dot"),
        )

    # Highlight G14 PASS points on CVRMSE series (most visible “success” metric)
    pass_x: list[int] = []
    pass_y: list[float] = []
    pass_text: list[str] = []
    for r, x in zip(numbered, xs, strict=False):
        if not _is_g14_pass(r):
            continue
        try:
            y = abs(float(r["cvrmse_elec_pct"])) if r.get("cvrmse_elec_pct") is not None else None
        except (TypeError, ValueError):
            y = None
        if y is None:
            try:
                y = abs(float(r["nmbe_elec_pct"])) if r.get("nmbe_elec_pct") is not None else None
            except (TypeError, ValueError):
                y = None
        if y is None:
            continue
        pass_x.append(int(x))
        pass_y.append(y)
        pass_text.append(str(r.get("run_id") or ""))
    if pass_x:
        fig.add_scatter(
            x=pass_x,
            y=pass_y,
            mode="markers+text",
            name="G14 PASS",
            text=["PASS"] * len(pass_x),
            textposition="top center",
            marker=dict(symbol="star", size=14, color="#2ca02c", line=dict(width=1, color="#145214")),
            customdata=pass_text,
            hovertemplate="<b>%{customdata}</b><br>G14 PASS<br>iter %{x}<extra></extra>",
        )

    if best and best.get("run") is not None:
        fig.add_annotation(
            x=int(best["run"]),
            y=0,
            yref="y domain",
            text=f"best: {best.get('run_id')}",
            showarrow=False,
            yanchor="bottom",
            font=dict(size=11),
        )

    x0, x1 = xs[0], xs[-1]
    fig.add_scatter(
        x=[x0, x1],
        y=[G14_NMBE_GATE, G14_NMBE_GATE],
        mode="lines",
        name=f"G14 |NMBE| gate ≤{G14_NMBE_GATE:g}%",
        line=dict(color="#d62728", width=2, dash="dash"),
        hovertemplate=f"ASHRAE G14 monthly |NMBE| gate ≤ {G14_NMBE_GATE:g}%<extra></extra>",
        showlegend=True,
    )
    fig.add_scatter(
        x=[x0, x1],
        y=[G14_CVRMSE_GATE, G14_CVRMSE_GATE],
        mode="lines",
        name=f"G14 CV(RMSE) gate ≤{G14_CVRMSE_GATE:g}%",
        line=dict(color="#8c564b", width=2, dash="dash"),
        hovertemplate=f"ASHRAE G14 monthly CV(RMSE) gate ≤ {G14_CVRMSE_GATE:g}%<extra></extra>",
        showlegend=True,
    )

    plotly_layout_clean(
        fig,
        title=f"G14 calibration across iterations{title_suffix} (per-building dial history)",
        height=height,
        yaxis_title="% error",
        xaxis_title="Iteration (oldest → newest) · tick = dial stem (hover = full run_id)",
    )
    fig.update_layout(
        legend=dict(
            title_text="Series (dashed = ASHRAE G14 monthly gates)",
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
        ),
    )
    fig.update_xaxes(
        tickmode="array",
        tickvals=xs,
        ticktext=ticktext,
        showgrid=True,
        gridcolor="rgba(0,0,0,0.06)",
    )
    fig.update_yaxes(rangemode="tozero", showgrid=True, gridcolor="rgba(0,0,0,0.08)")
    return fig
