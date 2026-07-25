"""Overview analytics → PNG for Engineering Findings DOCX (Plotly + Kaleido)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.reporting.models import ReportArtifacts


def overview_settings_from_context(ctx: dict[str, Any] | None) -> dict[str, Any]:
    """Lean settings block for DOCX §2 (no frames)."""
    ctx = ctx or {}

    def _ts(v: Any) -> str | None:
        if v is None:
            return None
        if hasattr(v, "strftime"):
            try:
                return v.strftime("%Y-%m-%d %H:%M")
            except Exception:
                return str(v)
        return str(v)

    return {
        "dataset_start": _ts(ctx.get("dataset_start")),
        "dataset_end": _ts(ctx.get("dataset_end")),
        "span_hours": ctx.get("span_hours"),
        "zone_lo_f": ctx.get("zone_lo_f"),
        "zone_hi_f": ctx.get("zone_hi_f"),
        "bare_min_occ_hours": ctx.get("bare_min_occ_hours"),
        "occupancy_schedule": ctx.get("occupancy_schedule"),
        "oat_err": ctx.get("oat_err"),
        "prefer_web_oat": ctx.get("prefer_web_oat"),
    }


def build_overview_context(
    *,
    frames: dict | None = None,
    role_map: dict | None = None,
    weather=None,
    prefer_web_oat: bool = True,
    oat_err: float = 5.0,
    chw_leave_max_f: float = 48.0,
    use_status_proof: bool = True,
    zone_lo_f: float = 70.0,
    zone_hi_f: float = 75.0,
    bare_min_occ_hours: float | None = None,
    occupancy_schedule: dict | None = None,
    dataset_start=None,
    dataset_end=None,
    span_hours: float | None = None,
) -> dict[str, Any]:
    """Assemble overview_context for reporting (may include heavy frames)."""
    return {
        "frames": frames or {},
        "role_map": role_map or {},
        "weather": weather,
        "prefer_web_oat": prefer_web_oat,
        "oat_err": oat_err,
        "chw_leave_max_f": chw_leave_max_f,
        "use_status_proof": use_status_proof,
        "zone_lo_f": zone_lo_f,
        "zone_hi_f": zone_hi_f,
        "bare_min_occ_hours": bare_min_occ_hours,
        "occupancy_schedule": occupancy_schedule,
        "dataset_start": dataset_start,
        "dataset_end": dataset_end,
        "span_hours": span_hours,
    }


def build_overview_charts(
    artifacts: ReportArtifacts,
    overview_context: dict[str, Any] | None,
    *,
    out_dir: Path,
) -> list[dict[str, Any]]:
    """Render Overview-tab analytics as PNGs when frames are present."""
    ctx = overview_context or {}
    frames = ctx.get("frames")
    if not frames:
        return []

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    role_map = ctx.get("role_map") or {}
    weather = ctx.get("weather")
    prefer_web = bool(ctx.get("prefer_web_oat", True))
    oat_err = float(ctx.get("oat_err") or 5.0)
    chw_leave = float(ctx.get("chw_leave_max_f") or 48.0)
    use_status = bool(ctx.get("use_status_proof", True))
    bare_min = ctx.get("bare_min_occ_hours")
    bare_min_f = float(bare_min) if bare_min is not None else None

    charts: list[dict[str, Any]] = []

    # BAS vs web OAT
    try:
        from app.charts import bas_vs_web_oat_overlay

        fig = bas_vs_web_oat_overlay(
            frames, role_map, weather=weather, oat_err=oat_err
        )
        if fig is not None:
            charts.append(
                _export_plotly(
                    fig,
                    "overview_bas_vs_web_oat",
                    out_dir,
                    title="BAS vs web outdoor-air temperature",
                )
            )
    except Exception as exc:
        charts.append(
            {"name": "overview_bas_vs_web_oat", "path": None, "export_error": str(exc)}
        )

    # Motor weekly by plant group
    try:
        from app.analytics import motor_run_hours_weekly
        from app.charts import motor_weekly_runtime_chart

        weekly = motor_run_hours_weekly(
            frames,
            role_map,
            weather=weather,
            prefer_web_oat=prefer_web,
            chw_leave_max_f=chw_leave,
        )
        titles = {
            "air": "Air side — supply fans",
            "boiler": "Boiler plant — HW pumps",
            "chiller": "Chiller plant — chillers, CHW/CW pumps, towers",
        }
        for plant, title in titles.items():
            sub = weekly[weekly["plant_group"] == plant] if weekly is not None and not weekly.empty else None
            if sub is None or sub.empty:
                continue
            fig = motor_weekly_runtime_chart(
                sub,
                title=title,
                min_hours_line=bare_min_f if plant == "air" else None,
                show_avg_oat=True,
            )
            if fig is None:
                continue
            charts.append(
                _export_plotly(
                    fig,
                    f"overview_motor_weekly_{plant}",
                    out_dir,
                    title=title,
                )
            )
    except Exception as exc:
        charts.append(
            {
                "name": "overview_motor_weekly",
                "path": None,
                "export_error": str(exc),
            }
        )

    # Mech cooling OAT bins
    try:
        from app.analytics import mech_cooling_oat_bins
        from app.charts import mech_cooling_oat_histogram

        bins = mech_cooling_oat_bins(
            frames,
            role_map,
            weather=weather,
            prefer_web_oat=prefer_web,
            chw_leave_max_f=chw_leave,
            use_status_proof=use_status,
        )
        fig = mech_cooling_oat_histogram(bins)
        if fig is not None:
            charts.append(
                _export_plotly(
                    fig,
                    "overview_mech_cooling_oat_bins",
                    out_dir,
                    title="Mechanical cooling run hours by outdoor-air temperature",
                )
            )
    except Exception as exc:
        charts.append(
            {
                "name": "overview_mech_cooling_oat_bins",
                "path": None,
                "export_error": str(exc),
            }
        )

    artifacts.overview_charts = [c for c in charts if c.get("path")]
    return charts


def _export_plotly(
    fig: Any, name: str, out_dir: Path, *, title: str | None = None
) -> dict[str, Any]:
    meta: dict[str, Any] = {"name": name, "path": None, "title": title or name}
    png = out_dir / f"{name}.png"
    try:
        fig.write_image(str(png), scale=2, width=900, height=480)
        meta["path"] = str(png)
    except Exception as exc:
        meta["export_error"] = str(exc)
        try:
            html = out_dir / f"{name}.html"
            fig.write_html(str(html), include_plotlyjs="cdn")
            meta["html"] = str(html)
        except Exception:
            pass
    return meta
