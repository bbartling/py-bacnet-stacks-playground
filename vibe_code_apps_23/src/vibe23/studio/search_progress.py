"""Grid-search progress helpers for the Studio training visualization."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..grid import GridCandidate, GridDimension, enumerate_grid
from ..residential.experiment import default_thermostat_candidates, default_thermostat_dimensions
from ..residential.model import PACKAGE_ROOT

FIXTURES = PACKAGE_ROOT / "fixtures" / "studio"
RANKING_SCHEMA = "vibe23.residential_grid_ranking.v1"


def season_dimension_defaults(season: str = "summer") -> tuple[GridDimension, ...]:
    """Return the default thermostat grid dimensions for a season (13×13 centers)."""
    return default_thermostat_dimensions(season=season)


def parse_dimension_values(text: str) -> tuple[float, ...]:
    """Parse a comma-separated dimension value list into floats."""
    raw = str(text or "").strip()
    if not raw:
        raise ValueError("dimension needs at least one value")
    values: list[float] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        values.append(float(token))
    if not values:
        raise ValueError("dimension needs at least one value")
    # Preserve order but reject duplicates after float parse.
    seen: set[float] = set()
    unique: list[float] = []
    for v in values:
        if v in seen:
            raise ValueError(f"duplicate dimension value: {v}")
        seen.add(v)
        unique.append(v)
    return tuple(unique)


def format_dimension_values(values: Sequence[Any]) -> str:
    return ", ".join(str(v) for v in values)


def dimensions_from_form(form: Mapping[str, str], *, season: str = "summer") -> tuple[GridDimension, ...]:
    """Build GridDimension tuple from a name→csv-string mapping."""
    defaults = season_dimension_defaults(season)
    dims: list[GridDimension] = []
    for dim in defaults:
        raw = form.get(dim.name)
        if raw is None or str(raw).strip() == "":
            dims.append(dim)
        else:
            dims.append(GridDimension(dim.name, parse_dimension_values(str(raw))))
    return tuple(dims)


def enumerate_from_form(form: Mapping[str, str], *, season: str = "summer") -> tuple[GridCandidate, ...]:
    return enumerate_grid(dimensions_from_form(form, season=season))


def load_grid_ranking(season: str = "summer", *, path: Path | str | None = None) -> dict[str, Any]:
    """Load a committed or session-local residential grid ranking JSON."""
    if path is not None:
        ranking_path = Path(path)
    else:
        key = season.strip().lower()
        name = (
            "winter_thermostat_grid_ranking.json"
            if key in {"winter", "jan", "january"}
            else "summer_thermostat_grid_ranking.json"
        )
        ranking_path = FIXTURES / name
    if not ranking_path.is_file():
        raise FileNotFoundError(f"grid ranking fixture missing: {ranking_path}")
    payload = json.loads(ranking_path.read_text(encoding="utf-8"))
    if payload.get("schema") != RANKING_SCHEMA:
        raise ValueError(f"unexpected ranking schema: {payload.get('schema')!r}")
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("ranking rows must be a non-empty list")
    required = {
        "candidate_id",
        "billing_cost",
        "peak_kw",
        "total_kwh",
        "comfort_ok",
        "soft_ok",
        "wall_seconds",
        "action_json",
    }
    for i, row in enumerate(rows):
        missing = required - set(row)
        if missing:
            raise ValueError(f"ranking row {i} missing keys: {sorted(missing)}")
    return payload


TWIN_EXPORT_SCHEMA = "vibe23.residential_grid_twin_export.v1"


def load_twin_export(season: str = "summer", *, path: Path | str | None = None) -> dict[str, Any]:
    """Load winner/baseline 288-point traces for Twin promote."""
    if path is not None:
        export_path = Path(path)
    else:
        key = season.strip().lower()
        name = (
            "winter_twin_export.json"
            if key in {"winter", "jan", "january"}
            else "summer_twin_export.json"
        )
        export_path = FIXTURES / name
    if not export_path.is_file():
        raise FileNotFoundError(f"twin export missing: {export_path}")
    payload = json.loads(export_path.read_text(encoding="utf-8"))
    if payload.get("schema") not in {TWIN_EXPORT_SCHEMA, None} and "baseline" not in payload:
        raise ValueError(f"unexpected twin export schema: {payload.get('schema')!r}")
    for role in ("baseline", "winner"):
        block = payload.get(role) or {}
        for key in ("facility_kw", "zone_temp_f"):
            series = block.get(key)
            if not isinstance(series, list) or len(series) < 24:
                raise ValueError(f"twin export {role}.{key} must be a series")
    return payload


def candidate_rows_for_animation(ranking: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return non-BASELINE rows in enumeration (ordinal) order for search replay."""
    rows = [dict(r) for r in ranking.get("rows") or [] if str(r.get("candidate_id")) != "BASELINE"]
    # Prefer ordinal from candidate_id GRID_XXXX_...
    def _ordinal(row: Mapping[str, Any]) -> int:
        cid = str(row.get("candidate_id", ""))
        if cid.startswith("GRID_") and len(cid) >= 9:
            try:
                return int(cid[5:9])
            except ValueError:
                return 10**9
        return 10**9

    rows.sort(key=_ordinal)
    return rows


def _is_feasible(row: Mapping[str, Any]) -> bool:
    cost = row.get("billing_cost")
    try:
        cost_f = float(cost)
    except (TypeError, ValueError):
        return False
    if not math.isfinite(cost_f):
        return False
    return bool(row.get("soft_ok")) and bool(row.get("comfort_ok"))


def _action_summary(action_json: str | Mapping[str, Any] | None) -> str:
    try:
        action = json.loads(action_json) if isinstance(action_json, str) else dict(action_json or {})
    except (TypeError, json.JSONDecodeError):
        return ""
    parts: list[str] = []
    for key in (
        "pre_center_f",
        "event_center_f",
        "pre_cool_f",
        "event_cool_f",
        "pre_heat_f",
        "event_heat_f",
        "pre_start_hour",
        "event_start",
        "event_end",
    ):
        if key in action:
            parts.append(f"{key.replace('_', ' ')} {action[key]}")
    return "  ".join(parts)


def search_progress_state(rows: Sequence[Mapping[str, Any]], evaluated: int) -> dict[str, Any]:
    """Compute ME-friendly progress counters for the first ``evaluated`` candidate rows.

    Returns keys:
      fraction, eplus_runs, total_runs, candidates_evaluated, catalog_size,
      feasible, rejected, wall_seconds_so_far, wall_seconds_projected,
      best_row, best_cost, log_lines
    """
    catalog = list(rows)
    n = len(catalog)
    evaluated = max(0, min(int(evaluated), n))
    prefix = catalog[:evaluated]
    feasible = sum(1 for r in prefix if _is_feasible(r))
    rejected = evaluated - feasible
    wall = sum(float(r.get("wall_seconds") or 0.0) for r in prefix)
    projected = None
    if evaluated > 0 and n > 0:
        projected = wall * (n / evaluated)

    best_row: dict[str, Any] | None = None
    best_cost = float("inf")
    log_lines: list[str] = []
    for i, row in enumerate(prefix, start=1):
        cid = str(row.get("candidate_id", f"cand_{i}"))
        wall_i = float(row.get("wall_seconds") or 0.0)
        action_bit = _action_summary(row.get("action_json"))
        ok = _is_feasible(row)
        try:
            cost = float(row.get("billing_cost"))
        except (TypeError, ValueError):
            cost = float("inf")
        if not ok:
            verdict = "REJECT - soft_ok/comfort gate failed" if not (
                bool(row.get("soft_ok")) and bool(row.get("comfort_ok"))
            ) else "REJECT - infeasible bill"
            cost_txt = "  ---  "
            log_lines.append(
                f"iter {i}/{n}  {cid}  {action_bit}   sim {wall_i:.1f}s   {cost_txt}   {verdict}"
            )
            continue
        if cost < best_cost:
            best_cost = cost
            best_row = dict(row)
            verdict = "ACCEPT - new best"
        else:
            verdict = f"keep {best_row.get('candidate_id') if best_row else '—'}"
        log_lines.append(
            f"iter {i}/{n}  {cid}  {action_bit}   sim {wall_i:.1f}s   ${cost:.2f}   {verdict}"
        )

    fraction = 0.0 if n == 0 else evaluated / n
    # Baseline EnergyPlus run + one per candidate.
    eplus_runs = 1 + evaluated
    total_runs = 1 + n
    return {
        "fraction": float(fraction),
        "eplus_runs": eplus_runs,
        "total_runs": total_runs,
        "candidates_evaluated": evaluated,
        "catalog_size": n,
        "feasible": feasible,
        "rejected": rejected,
        "wall_seconds_so_far": float(wall),
        "wall_seconds_projected": None if projected is None else float(projected),
        "best_row": best_row,
        "best_cost": None if best_row is None else float(best_cost),
        "log_lines": log_lines,
    }


def algorithm_pseudocode(*, season: str, dims: Sequence[GridDimension], n: int) -> str:
    searched = [d for d in dims if d.name in {"pre_center_f", "event_center_f"}]
    dim_bits = ", ".join(f"{d.name}={{{format_dimension_values(d.values)}}}" for d in searched)
    return "\n".join(
        [
            "freeze  S = {model_sha, weather_sha, tariff_sha, eplus_version}",
            "deadband 2F around center: heat=c-1, cool=c+1  (default center=72F)",
            f"grid    D = [{dim_bits}]   # N = {n}",
            "hours   fixed to TOU peak window (summer 13→16–21, winter 5→6–9)",
            "for c in itertools.product(*D):",
            '    id = f"GRID_{ordinal:04d}_{sha256(c)[:12]}"',
            "    e  = EnergyPlus(c, S)                 # ~0.7–1s / candidate",
            "    if not soft_ok or zone outside comfort band: score = inf; continue",
            "    purchased = battery_dispatch(e.kw, TOU)   # pure Python, free",
            "    score[c] = billing_cost(purchased)",
            "rank by billing_cost; promote winner → Twin replay",
        ]
    )


def form_matches_fixture_catalog(form: Mapping[str, str], *, season: str) -> bool:
    """True when the form dimensions match the default catalog used by the fixture."""
    try:
        live = enumerate_from_form(form, season=season)
        default = default_thermostat_candidates(season=season)
    except ValueError:
        return False
    if len(live) != len(default):
        return False
    return all(a.candidate_id == b.candidate_id for a, b in zip(live, default, strict=True))


def qtable_matrix(
    rows: Sequence[Mapping[str, Any]],
    *,
    evaluated: int | None = None,
) -> dict[str, Any]:
    """Build a Q-table-style matrix keyed by (pre_center_f, event_center_f).

    Cells are $/day when feasible, None when rejected / not yet evaluated.
    """
    anim = [r for r in rows if str(r.get("candidate_id")) != "BASELINE"]
    if evaluated is not None:
        anim = anim[: max(0, int(evaluated))]

    pre_vals: set[float] = set()
    event_vals: set[float] = set()
    cells: dict[tuple[float, float], float | None] = {}

    for row in anim:
        try:
            action = (
                json.loads(row["action_json"])
                if isinstance(row.get("action_json"), str)
                else dict(row.get("action") or {})
            )
        except (TypeError, json.JSONDecodeError):
            action = {}
        pre = float(action.get("pre_center_f", row.get("pre_center_f", float("nan"))))
        ev = float(action.get("event_center_f", row.get("event_center_f", float("nan"))))
        if not (math.isfinite(pre) and math.isfinite(ev)):
            continue
        pre_vals.add(pre)
        event_vals.add(ev)
        cells[(pre, ev)] = float(row["billing_cost"]) if _is_feasible(row) else None

    pre_axis = sorted(pre_vals)
    event_axis = sorted(event_vals)
    z = [[cells.get((p, e)) for e in event_axis] for p in pre_axis]
    return {
        "pre_centers": pre_axis,
        "event_centers": event_axis,
        "costs": z,
        "n_filled": len(cells),
    }


__all__ = [
    "algorithm_pseudocode",
    "candidate_rows_for_animation",
    "dimensions_from_form",
    "enumerate_from_form",
    "form_matches_fixture_catalog",
    "format_dimension_values",
    "load_grid_ranking",
    "load_twin_export",
    "parse_dimension_values",
    "qtable_matrix",
    "search_progress_state",
    "season_dimension_defaults",
]
