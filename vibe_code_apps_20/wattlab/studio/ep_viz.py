"""EnergyPlusAPIHelper-08-style viz helpers (post-sim, Docker outputs only).

Replicates the classic 5Zone floor-plan heatmap + OA chart patterns from
``08_server_advanced`` without host ``pyenergyplus``. Zone geometry uses the
standard DOE 5ZoneAirCooled compass layout (SPACE1-1…SPACE5-1); other zone
names are mapped by discovery order or nickname heuristics.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pandas as pd

# Classic 5ZoneAirCooled floor-plan vertices (same layout as APIHelper 08 HTML).
# Coordinates are unitless; Plotly scales them.
ZONE_VERTICES: dict[str, list[list[float]]] = {
    "north": [[0, 3], [1, 2], [4, 2], [5, 3]],
    "south": [[0, 0], [5, 0], [4, 1], [1, 1]],
    "east": [[5, 3], [4, 2], [4, 1], [5, 0]],
    "west": [[0, 3], [0, 0], [1, 1], [1, 2]],
    "center": [[1, 1], [1, 2], [4, 2], [4, 1]],
}

# Prototype zone name → compass role (EnergyPlus 5Zone convention, not a site id).
PROTOTYPE_ZONE_ROLES: dict[str, str] = {
    "SPACE1-1": "south",
    "SPACE2-1": "west",
    "SPACE3-1": "east",
    "SPACE4-1": "north",
    "SPACE5-1": "center",
    "space1-1": "south",
    "space2-1": "west",
    "space3-1": "east",
    "space4-1": "north",
    "space5-1": "center",
}


def map_zones_to_roles(zone_names: list[str]) -> dict[str, str]:
    """Map discovered zone names → north/south/east/west/center."""
    roles: dict[str, str] = {}
    remaining = ["south", "west", "east", "north", "center"]
    for name in zone_names:
        key = name.strip()
        role = PROTOTYPE_ZONE_ROLES.get(key) or PROTOTYPE_ZONE_ROLES.get(key.upper())
        if role and role not in roles.values():
            roles[key] = role
            if role in remaining:
                remaining.remove(role)
    for name in zone_names:
        if name in roles:
            continue
        low = name.lower()
        for role in list(remaining):
            if role in low:
                roles[name] = role
                remaining.remove(role)
                break
    for name in zone_names:
        if name in roles or not remaining:
            continue
        roles[name] = remaining.pop(0)
    return roles


def rgb_from_temperature(zone_temp: float, *, min_temp: float = 20.0, max_temp: float = 24.0) -> str:
    t = max(min_temp, min(max_temp, float(zone_temp)))
    ratio = (t - min_temp) / (max_temp - min_temp) if max_temp > min_temp else 0.5
    red = int(ratio * 255)
    blue = int(255 - red)
    return f"rgb({red},0,{blue})"


def zone_mean_by_role(ts: Any) -> dict[str, float]:
    """Return {role: mean_temp_c} from an EplusTimeseries."""
    means = ts.zone_mean_temps() if ts is not None else pd.DataFrame()
    if means.empty:
        return {}
    names = [str(z) for z in means["zone"].tolist()]
    roles = map_zones_to_roles(names)
    out: dict[str, float] = {}
    for _, row in means.iterrows():
        role = roles.get(str(row["zone"]))
        if role:
            out[role] = float(row["mean_c"])
    return out


def floor_plan_figure(role_temps: dict[str, float]):
    """Plotly floor-plan heatmap matching APIHelper 08 zone layout."""
    import plotly.graph_objects as go

    fig = go.Figure()
    for role, vertices in ZONE_VERTICES.items():
        temp = role_temps.get(role)
        fill = rgb_from_temperature(temp) if temp is not None else "rgb(200,200,200)"
        xs = [v[0] for v in vertices] + [vertices[0][0]]
        ys = [v[1] for v in vertices] + [vertices[0][1]]
        label = f"{role}: {temp:.1f} C" if temp is not None else f"{role}: n/a"
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                fill="toself",
                fillcolor=fill,
                line={"color": "#000", "width": 1},
                mode="lines",
                name=label,
                hoverinfo="name",
            )
        )
    fig.update_layout(
        title="Zone air temperatures (classic 5Zone floor plan)",
        xaxis={"visible": False, "scaleanchor": "y"},
        yaxis={"visible": False},
        showlegend=True,
        height=360,
        margin={"l": 20, "r": 20, "t": 40, "b": 20},
    )
    return fig


def multifloor_office_figure(
    role_temps: dict[str, float],
    *,
    n_floors: int,
    highlight_floor: int | None = None,
):
    """Stacked floor-plate schematic for multi-story office screening.

    Each plate reuses the classic 5Zone compass vertices; temps are mapped from
    the single-story prototype CSV (honesty: not site CAD / not true multi-floor IDF).
    """
    import plotly.graph_objects as go

    n = max(2, int(n_floors))
    fig = go.Figure()
    gap = 0.35
    plate_h = 3.0
    show_floors = list(range(1, n + 1))
    if n > 8 and highlight_floor is not None:
        # Optional selector: show all but emphasize one; still draw all for ≤8
        pass
    for fi, floor in enumerate(show_floors):
        y_off = fi * (plate_h + gap)
        emph = highlight_floor is None or floor == int(highlight_floor)
        for role, vertices in ZONE_VERTICES.items():
            temp = role_temps.get(role)
            fill = rgb_from_temperature(temp) if temp is not None else "rgb(200,200,200)"
            if not emph:
                fill = "rgba(180,180,180,0.35)"
            xs = [v[0] for v in vertices] + [vertices[0][0]]
            ys = [v[1] + y_off for v in vertices] + [vertices[0][1] + y_off]
            label = f"F{floor} {role}"
            if temp is not None and emph:
                label = f"F{floor} {role}: {temp:.1f} C"
            fig.add_trace(
                go.Scatter(
                    x=xs,
                    y=ys,
                    fill="toself",
                    fillcolor=fill,
                    line={"color": "#222" if emph else "#999", "width": 1},
                    mode="lines",
                    name=label,
                    hoverinfo="name",
                    showlegend=(floor == show_floors[-1]),
                )
            )
        # Floor label
        fig.add_annotation(
            x=-0.4,
            y=y_off + plate_h / 2,
            text=f"F{floor}",
            showarrow=False,
            font={"size": 11},
        )
    fig.update_layout(
        title=f"Schematic massing — {n}-story office (prototype zones per plate)",
        xaxis={"visible": False, "scaleanchor": "y"},
        yaxis={"visible": False},
        showlegend=True,
        height=min(900, 200 + n * 90),
        margin={"l": 40, "r": 20, "t": 50, "b": 20},
    )
    return fig


MULTIFLOOR_HONESTY = (
    "Schematic massing for N-story office screening — not site CAD; "
    "prototype 5Zone roles mapped to each plate until a multi-floor IDF exists."
)


def outdoor_figure(outdoor: pd.DataFrame):
    """OA drybulb over sim timesteps (08 right-hand chart)."""
    import plotly.graph_objects as go

    df = outdoor.copy()
    if df.empty or "outdoor_db_c" not in df.columns:
        fig = go.Figure()
        fig.update_layout(title="Outdoor drybulb (no data)")
        return fig
    if "timestamp" not in df.columns:
        df = df.reset_index(drop=True)
        df["timestamp"] = df.index.astype(str)
    # Downsample for UI
    if len(df) > 2000:
        stride = max(1, len(df) // 2000)
        df = df.iloc[::stride]
    fig = go.Figure(
        data=[
            go.Scatter(
                x=list(range(len(df))),
                y=df["outdoor_db_c"],
                mode="lines",
                name="Outdoor DBT C",
                line={"width": 1},
            )
        ]
    )
    fig.update_layout(
        title="Outdoor air drybulb (post-sim)",
        xaxis_title="timestep",
        yaxis_title="C",
        height=280,
        margin={"l": 40, "r": 20, "t": 40, "b": 40},
    )
    return fig


def read_run_progress(run_dir: Path) -> dict[str, Any]:
    """Load progress/log/manifest for the 08 left-hand manage card."""
    run_dir = Path(run_dir)
    out: dict[str, Any] = {
        "run_id": run_dir.name,
        "progress": 0,
        "status": "unknown",
        "log_tail": "",
        "manifest": {},
        "replay": False,
    }
    manifest_path = run_dir / "run_manifest.json"
    if manifest_path.is_file():
        try:
            out["manifest"] = json.loads(manifest_path.read_text(encoding="utf-8"))
            out["status"] = str(out["manifest"].get("status") or out["status"])
            out["run_id"] = str(out["manifest"].get("run_id") or out["run_id"])
        except (OSError, json.JSONDecodeError):
            pass
    progress_path = run_dir / "progress.json"
    if progress_path.is_file():
        try:
            prog = json.loads(progress_path.read_text(encoding="utf-8"))
            out["progress"] = int(prog.get("percent") or prog.get("progress") or 0)
            out["status"] = str(prog.get("status") or out["status"])
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
    elif out["status"] in {"ok", "success", "completed", "complete"}:
        out["progress"] = 100
    for log_name in ("eplusout.err", "energyplus.log", "console.log", "run.log"):
        lp = run_dir / log_name
        if lp.is_file():
            try:
                text = lp.read_text(encoding="utf-8", errors="replace")
                out["log_tail"] = text[-4000:]
                break
            except OSError:
                continue
    if (run_dir / "REPLAY.txt").is_file() or out["manifest"].get("replay"):
        out["replay"] = True
        out["progress"] = max(out["progress"], 100)
        out["status"] = out["status"] if out["status"] != "unknown" else "replay"
    return out


def list_iteration_runs(runs_root: Path, limit: int = 20) -> list[dict[str, Any]]:
    root = Path(runs_root)
    if not root.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for d in sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not d.is_dir():
            continue
        info = read_run_progress(d)
        info["dir"] = str(d)
        info["has_eplusout"] = (d / "eplusout.csv").is_file() or bool(
            list(d.glob("**/eplusout.csv"))
        )
        rows.append(info)
        if len(rows) >= limit:
            break
    return rows


def publish_run_for_studio(
    source: Path | str,
    *,
    run_id: str | None = None,
    report: dict[str, Any] | None = None,
    dest_root: Path | None = None,
) -> Path:
    """Copy an EnergyPlus / easy-button artifact tree into Studio ``runs/<id>/``.

    Agents and CLI write here so the human Twin page can render APIHelper-08
    panes (progress, OA chart, classic 5Zone floor plan) in the browser.
    Prefers ``sim_baseline/eplusout.csv`` when present.
    """
    from wattlab.studio.workspace import runs_dir

    src = Path(source)
    if not src.exists():
        raise FileNotFoundError(f"publish_run_for_studio: missing {src}")

    rid = run_id or src.name.replace("wattlab_", "") or src.name
    dest = Path(dest_root) if dest_root is not None else (runs_dir() / rid)
    dest.mkdir(parents=True, exist_ok=True)

    # Locate best eplusout.csv (baseline first)
    candidates: list[Path] = []
    if src.is_file() and src.name.startswith("eplusout") and src.suffix == ".csv":
        candidates.append(src)
    elif src.is_dir():
        for prefer in ("sim_baseline/eplusout.csv", "eplusout.csv"):
            p = src / prefer
            if p.is_file():
                candidates.append(p)
        candidates.extend(sorted(src.rglob("eplusout.csv")))
    if candidates:
        shutil.copy2(candidates[0], dest / "eplusout.csv")

    for name in ("eplusout.err", "run_manifest.json", "progress.json", "wattlab_report.json"):
        p = src / name if src.is_dir() else None
        if p is not None and p.is_file():
            shutil.copy2(p, dest / name)

    if report is not None:
        (dest / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    elif src.is_dir() and (src / "wattlab_report.json").is_file() and not (dest / "report.json").is_file():
        shutil.copy2(src / "wattlab_report.json", dest / "report.json")

    if not (dest / "run_manifest.json").is_file():
        (dest / "run_manifest.json").write_text(
            json.dumps(
                {
                    "run_id": rid,
                    "status": "SUCCESS" if (dest / "eplusout.csv").is_file() else "partial",
                    "published_from": str(src),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    if not (dest / "progress.json").is_file():
        (dest / "progress.json").write_text(
            json.dumps(
                {
                    "percent": 100 if (dest / "eplusout.csv").is_file() else 0,
                    "status": "published",
                }
            ),
            encoding="utf-8",
        )

    # Pointer so Twin auto-selects the latest agent publish
    pointer = dest.parent / "CURRENT_RUN.txt"
    pointer.write_text(str(dest.resolve()), encoding="utf-8")
    # Best-effort: keep studio_bootstrap.json preferred_run_id in sync.
    try:
        from wattlab.studio.bootstrap import upsert_bootstrap_preferred_run

        upsert_bootstrap_preferred_run(rid)
    except Exception:  # noqa: BLE001
        pass
    # Best-effort world-writable so host agents can archive without root.
    try:
        import os

        os.chmod(dest, 0o777)
        for child in dest.rglob("*"):
            try:
                os.chmod(child, 0o666 if child.is_file() else 0o777)
            except OSError:
                pass
    except OSError:
        pass
    return dest


def install_demo_replay(run_dir: Path, fixture_csv: Path) -> Path:
    """Copy fixture eplusout into a run dir labeled as demo replay (no Docker)."""
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    dest = run_dir / "eplusout.csv"
    dest.write_bytes(Path(fixture_csv).read_bytes())
    (run_dir / "REPLAY.txt").write_text(
        "Demo replay from fixture eplusout.csv — not a live EnergyPlus run.\n",
        encoding="utf-8",
    )
    (run_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "run_id": run_dir.name,
                "status": "replay",
                "replay": True,
                "source": str(fixture_csv),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (run_dir / "progress.json").write_text(
        json.dumps({"percent": 100, "status": "replay"}),
        encoding="utf-8",
    )
    pointer = run_dir.parent / "CURRENT_RUN.txt"
    pointer.write_text(str(run_dir.resolve()), encoding="utf-8")
    return dest


__all__ = [
    "PROTOTYPE_ZONE_ROLES",
    "ZONE_VERTICES",
    "floor_plan_figure",
    "install_demo_replay",
    "list_iteration_runs",
    "map_zones_to_roles",
    "outdoor_figure",
    "publish_run_for_studio",
    "read_run_progress",
    "rgb_from_temperature",
    "zone_mean_by_role",
]
