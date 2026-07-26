"""ECMs — Excel engineering notebooks only (BUG-043)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from wattlab.studio.g14_history import assign_run_numbers, iter_g14_history, pick_best_g14_run
from wattlab.studio.workspace import reports_dir, runs_dir


def _load_run_report(run_dir: Path | str | None) -> dict[str, Any]:
    if not run_dir:
        return {}
    root = Path(run_dir)
    for name in ("report.json", "wattlab_report.json", "calibration_scorecard.json"):
        p = root / name
        if p.is_file():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                return data if isinstance(data, dict) else {}
            except (OSError, json.JSONDecodeError, TypeError):
                continue
    return {}


def _enrich_profile_for_proxies(profile: dict[str, Any]) -> dict[str, Any]:
    """Merge answers / hard_size nameplate into a profile copy for ESCO bins."""
    out = dict(profile)
    answers = st.session_state.get("studio_answers")
    if isinstance(answers, dict):
        for key in (
            "cooling_tons",
            "fan_hp",
            "supply_fan_hp",
            "conditioned_floor_area_ft2",
            "floor_area_ft2",
        ):
            if out.get(key) is None and answers.get(key) is not None:
                out[key] = answers[key]
    hard = st.session_state.get("studio_hard_size")
    if isinstance(hard, dict) and not isinstance(out.get("hard_size"), dict):
        out["hard_size"] = hard
    return out


def _render_baseline_run_picker() -> None:
    """Selectbox of Twin runs; prefer savings_by_measure (E+ measures)."""
    st.subheader("Twin baseline run")
    st.caption(
        "Notebook Compare uses Twin ``savings_by_measure`` when present. "
        "Prefer a run tagged **E+ measures**. Easy-button EP cascades need Docker "
        "socket + EnergyPlus on the host (see AGENT_TOOLS.md)."
    )
    try:
        rows = assign_run_numbers(iter_g14_history(runs_dir(), limit=40))
    except Exception:
        rows = []
    if not rows:
        st.info("No published Twin runs yet — calibrate on Twin first.")
        return

    best = pick_best_g14_run(rows)
    opts = [str(r["dir"]) for r in rows if r.get("dir")]
    by_dir = {str(r["dir"]): r for r in rows if r.get("dir")}

    has_sbm: dict[str, bool] = {}
    for d in opts:
        rep = _load_run_report(d)
        has_sbm[d] = bool(rep.get("savings_by_measure"))

    stored = st.session_state.get("studio_ecm_baseline_run")
    if stored and str(stored) in opts:
        default_dir = str(stored)
    elif best and best.get("dir"):
        default_dir = str(best["dir"])
    else:
        default_dir = opts[-1] if opts else None
    if default_dir and not has_sbm.get(default_dir):
        with_sbm = [d for d in opts if has_sbm.get(d)]
        if with_sbm:
            default_dir = with_sbm[-1]

    if default_dir and "studio_ecm_baseline_pick" not in st.session_state:
        st.session_state["studio_ecm_baseline_pick"] = default_dir
    cur = st.session_state.get("studio_ecm_baseline_pick")
    if cur is not None and cur not in opts:
        st.session_state.pop("studio_ecm_baseline_pick", None)
        if default_dir:
            st.session_state["studio_ecm_baseline_pick"] = default_dir

    def _label(d: str) -> str:
        r = by_dir.get(d) or {}
        n = r.get("run")
        rid = r.get("run_id") or Path(d).name
        pf = r.get("pass_fail") or "—"
        tag = " · best G14" if best and str(best.get("dir")) == d else ""
        ecm = " · E+ measures" if has_sbm.get(d) else " · ESCO-only"
        return f"#{n} · {rid} · {pf}{tag}{ecm}" if n is not None else f"{rid} · {pf}{tag}{ecm}"

    pick = st.selectbox(
        "Baseline Twin run",
        options=opts,
        format_func=_label,
        key="studio_ecm_baseline_pick",
    )
    if pick:
        st.session_state["studio_ecm_baseline_run"] = pick
        report = _load_run_report(pick)
        score = {}
        sp = Path(pick) / "calibration_scorecard.json"
        if sp.is_file():
            try:
                score = json.loads(sp.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, TypeError):
                score = {}
        if report:
            st.session_state["studio_report"] = {
                **(st.session_state.get("studio_report") or {}),
                **report,
            }
        meta = by_dir.get(pick) or {}
        st.caption(
            f"Active ECM baseline: #{meta.get('run')} · {meta.get('run_id')} · "
            f"G14={meta.get('pass_fail') or (score.get('utility_bills') or {}).get('pass_fail') or '—'} "
            f"· `{Path(pick).name}`"
        )
        if not has_sbm.get(pick):
            st.warning(
                "This Twin run has no ``savings_by_measure`` — notebook Compare will be "
                "mostly YELLOW (ESCO-only). Pick a run tagged **E+ measures** when available."
            )


def _preview_sheet_frame(path: Path, sheet: str, *, mode: str) -> pd.DataFrame | None:
    """Build a Values or Formulas preview frame (never blank formula cells)."""
    from wattlab.notebooks.builder import preview_sheet_rows

    if mode == "values":
        # Prefer formula-text overlay for formula cells + numeric caches
        formula_rows = preview_sheet_rows(path, sheet, max_rows=50, data_only=False)
        value_rows = preview_sheet_rows(path, sheet, max_rows=50, data_only=True)
        if not formula_rows:
            return None
        header = formula_rows[0]
        body: list[list[Any]] = []
        for i, frow in enumerate(formula_rows[1:]):
            vrow = value_rows[i + 1] if value_rows and i + 1 < len(value_rows) else []
            merged: list[Any] = []
            for j, cell in enumerate(frow):
                if isinstance(cell, str) and cell.startswith("="):
                    # Values mode: show cache-friendly display — use data_only if present else keep formula
                    vc = vrow[j] if j < len(vrow) else None
                    merged.append(vc if vc is not None else cell)
                else:
                    merged.append(cell)
            body.append(merged)
        return pd.DataFrame(body, columns=header)

    rows = preview_sheet_rows(path, sheet, max_rows=50, data_only=False)
    if not rows:
        return None
    return pd.DataFrame(rows[1:], columns=rows[0])


def _render_engineering_notebook(profile: dict[str, Any]) -> None:
    """Primary ECM deliverable: package Excel notebook (Values/Formulas + download)."""
    from wattlab.notebooks import (
        build_and_save_notebook,
        list_notebook_packages,
    )
    from wattlab.notebooks.builder import refresh_notebook_caches, validate_notebook
    from wattlab.studio.ecm_scenario import (
        default_ecm_scenario_path,
        load_ecm_scenario,
        save_ecm_scenario,
    )

    st.subheader("Engineering notebook (Excel)")
    st.caption(
        "Excel is the ECM contract: build/refresh → Values + Formulas preview → download. "
        "Agents: `wattlab notebook build|prefill|refresh-caches|show-formulas|validate|summarize`."
    )
    st.markdown(
        "[ESCO formula map (GitHub)]"
        "(https://github.com/bbartling/py-bacnet-stacks-playground/blob/develop/"
        "vibe_code_apps_20/docs/ESCO_SPREADSHEET_CALCS.md)"
    )
    pkgs = list_notebook_packages()
    by_id = {p.id: p for p in pkgs}
    labels = {p.id: p.label for p in pkgs}
    pick = st.selectbox(
        "Package",
        [p.id for p in pkgs],
        format_func=lambda k: labels.get(k, k),
        key="ecm_notebook_package",
    )
    pkg = by_id[pick]
    st.caption(f"{pkg.honesty} · {len(pkg.measure_ids)} measures · catalog `{pkg.catalog_package}`")

    out_dir = reports_dir() / "notebooks"
    c1, c2 = st.columns(2)
    with c1:
        build_clicked = st.button("Build / refresh notebook", type="primary", key="ecm_notebook_build")
    with c2:
        refresh_clicked = st.button("Refresh caches only", key="ecm_notebook_refresh_caches")

    if build_clicked:
        try:
            proxy_profile = _enrich_profile_for_proxies(profile)
            report = st.session_state.get("studio_report") or {}
            run = st.session_state.get("studio_ecm_baseline_run")
            if run and not report.get("savings_by_measure"):
                report = {**report, **_load_run_report(run)}
            written = build_and_save_notebook(
                pick,
                out_dir,
                profile=proxy_profile,
                report=report if isinstance(report, dict) else {},
                write_manifest=True,
            )
            st.session_state["studio_notebook_path"] = str(written["xlsx"])
            st.session_state["studio_notebook_manifest"] = str(written.get("manifest") or "")
            v = validate_notebook(written["xlsx"])
            for w in v.get("warnings") or []:
                st.warning(w)
            scen = load_ecm_scenario()
            scen["notebook_package_id"] = pick
            scen["notebook_path"] = str(written["xlsx"])
            scen["selected_ecm_ids"] = list(pkg.measure_ids)
            save_ecm_scenario(scen)
            st.success(f"Notebook → {written['xlsx']}")
        except Exception as exc:
            st.error(f"Notebook build failed: {exc}")
            return

    xlsx = st.session_state.get("studio_notebook_path")
    if not xlsx or not Path(str(xlsx)).is_file():
        candidate = out_dir / f"{pick}.xlsx"
        if candidate.is_file():
            xlsx = str(candidate)
            st.session_state["studio_notebook_path"] = xlsx

    if refresh_clicked:
        if not xlsx or not Path(str(xlsx)).is_file():
            st.warning("Build a notebook first, then refresh caches.")
        else:
            try:
                result = refresh_notebook_caches(xlsx)
                st.success(f"Caches refreshed: {result.get('updated_cells', 0)} cells")
            except Exception as exc:
                st.error(f"refresh-caches failed: {exc}")

    if xlsx and Path(str(xlsx)).is_file():
        path = Path(str(xlsx))
        mode = st.radio(
            "Preview mode",
            options=["formulas", "values"],
            format_func=lambda k: "Formulas (Excel code)" if k == "formulas" else "Values (caches / static)",
            horizontal=True,
            key="ecm_notebook_preview_mode",
            help="Formulas = exact cell formula text. Values = numeric caches where Excel has not calc'd.",
        )
        tabs = st.tabs(["Inputs", "Compare", "ROI_Capital"])
        for tab, sheet in zip(tabs, ("Inputs", "Compare", "ROI_Capital")):
            with tab:
                df = _preview_sheet_frame(path, sheet, mode=mode)
                if df is None or df.empty:
                    st.caption(f"Sheet `{sheet}` empty or missing.")
                else:
                    st.dataframe(df, width="stretch", hide_index=True)
        st.download_button(
            "Download engineering notebook (.xlsx)",
            data=path.read_bytes(),
            file_name=path.name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="ecm_dl_notebook_xlsx",
            type="primary",
        )
        man = path.parent / f"{path.stem}.notebook_manifest.json"
        if man.is_file():
            st.download_button(
                "Download notebook_manifest.json (agents)",
                data=man.read_bytes(),
                file_name=man.name,
                mime="application/json",
                key="ecm_dl_notebook_manifest",
            )
        st.caption(f"Also on disk: `{path}` · scenario → `{default_ecm_scenario_path()}`")


def render() -> None:
    st.header("ECMs — engineering notebooks")
    st.caption(
        "Excel is the primary ECM deliverable (one package → one `.xlsx`). "
        "No Easy Buttons / capital-plan / client DOCX on this page — use Twin + "
        "`wattlab easy-button` / `wattlab notebook` CLIs for EP cascades."
    )

    profile = st.session_state.get("studio_profile")
    if not profile:
        answers = st.session_state.get("studio_answers")
        st.info(
            "Resolve a profile on **Twin / calibrate** first — or bootstrap with "
            "`answers_path` so Re-apply builds `studio_profile` automatically. "
            "Agents: `wattlab notebook build --package controls_first --out reports/notebooks/`."
        )
        if isinstance(answers, dict):
            st.caption(
                f"answers.json present (type={answers.get('building_type')}, "
                f"city={answers.get('city')}) — Re-apply bootstrap to unlock ECMs."
            )
        return

    _render_baseline_run_picker()
    st.divider()
    _render_engineering_notebook(profile)
