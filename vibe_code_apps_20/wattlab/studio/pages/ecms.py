"""ECMs — disk mirror of agent-owned Excel notebooks (BUG-050)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from wattlab.studio.workspace import reports_dir


def _preview_sheet_frame(path: Path, sheet: str, *, mode: str) -> pd.DataFrame | None:
    """Build a Values or Formulas preview frame (never blank formula cells)."""
    from wattlab.notebooks.builder import preview_sheet_rows

    if mode == "values":
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


def _list_notebook_files(out_dir: Path) -> list[Path]:
    if not out_dir.is_dir():
        return []
    return sorted(out_dir.glob("*.xlsx"))


def _enrich_profile(profile: dict[str, Any] | None) -> dict[str, Any]:
    out = dict(profile or {})
    answers = st.session_state.get("studio_answers")
    if isinstance(answers, dict):
        for key in (
            "display_name",
            "project_id",
            "building_name",
            "building",
            "name",
            "building_id",
            "cooling_tons",
            "fan_hp",
            "supply_fan_hp",
            "conditioned_floor_area_ft2",
            "floor_area_ft2",
        ):
            if out.get(key) is None and answers.get(key) is not None:
                out[key] = answers[key]
    return out


def _render_mirror() -> None:
    from wattlab.notebooks import list_notebook_packages
    from wattlab.notebooks.builder import (
        agent_build_notebook,
        refresh_notebook_caches,
        validate_notebook,
    )
    from wattlab.studio.ecm_scenario import (
        default_ecm_scenario_path,
        load_ecm_scenario,
        save_ecm_scenario,
    )

    st.subheader("Engineering notebook (Excel mirror)")
    st.caption(
        "Agent owns the `.xlsx` under `reports/notebooks/`. "
        "Refresh the browser or **Reload from disk** to see the latest bytes. "
        "CLI: `wattlab notebook agent-build|prefill|refresh-caches|sync-from-twin|show-formulas`."
    )
    st.markdown(
        "[ESCO formula map (GitHub)]"
        "(https://github.com/bbartling/py-bacnet-stacks-playground/blob/develop/"
        "vibe_code_apps_20/docs/ESCO_SPREADSHEET_CALCS.md)"
    )

    out_dir = reports_dir() / "notebooks"
    out_dir.mkdir(parents=True, exist_ok=True)
    scen = load_ecm_scenario()
    pkgs = list_notebook_packages()
    by_id = {p.id: p for p in pkgs}
    labels = {p.id: p.label for p in pkgs}

    on_disk = _list_notebook_files(out_dir)
    disk_stems = {p.stem: p for p in on_disk}

    default_pkg = scen.get("notebook_package_id") or (pkgs[0].id if pkgs else "controls_first")
    if default_pkg not in by_id and disk_stems:
        default_pkg = next(iter(disk_stems))
    pkg_ids = [p.id for p in pkgs]
    for stem in disk_stems:
        if stem not in pkg_ids:
            pkg_ids.append(stem)

    if "ecm_notebook_package" not in st.session_state and default_pkg in pkg_ids:
        st.session_state["ecm_notebook_package"] = default_pkg

    pick = st.selectbox(
        "Package / file",
        pkg_ids,
        format_func=lambda k: labels.get(k, k) + (" · on disk" if k in disk_stems else " · not built yet"),
        key="ecm_notebook_package",
    )
    pkg = by_id.get(pick)
    if pkg:
        st.caption(f"{pkg.honesty} · {len(pkg.measure_ids)} catalog measures · `{pkg.catalog_package}`")
    if scen.get("status"):
        st.caption(f"Scenario: {scen.get('status')} · twin={scen.get('twin_run') or '—'}")

    c1, c2, c3 = st.columns(3)
    with c1:
        reload_clicked = st.button("Reload from disk", key="ecm_notebook_reload")
    with c2:
        refresh_clicked = st.button("Refresh caches only", key="ecm_notebook_refresh_caches")
    with c3:
        rebuild_clicked = st.button(
            "Rebuild from scenario.json",
            key="ecm_notebook_rebuild_scenario",
            help="Same helper as `wattlab notebook agent-build --scenario …`",
        )

    if reload_clicked:
        st.session_state.pop("studio_notebook_path", None)
        st.session_state.pop("studio_notebook_manifest", None)
        st.info("Session path cleared — re-reading disk.")

    if rebuild_clicked:
        try:
            profile = _enrich_profile(st.session_state.get("studio_profile"))
            scen = load_ecm_scenario()
            package_id = scen.get("notebook_package_id") or pick
            ecms = scen.get("selected_ecm_ids") or None
            twin = scen.get("twin_run")
            report: dict[str, Any] = {}
            if twin:
                root = Path(str(twin))
                if not root.is_absolute():
                    # allow run id relative to runs/
                    from wattlab.studio.workspace import runs_dir

                    cand = runs_dir() / str(twin)
                    if cand.is_dir():
                        root = cand
                for name in ("report.json", "wattlab_report.json", "calibration_scorecard.json"):
                    rp = root / name if root.is_dir() else Path()
                    if rp.is_file():
                        try:
                            data = json.loads(rp.read_text(encoding="utf-8"))
                            if isinstance(data, dict):
                                report = data
                        except (OSError, json.JSONDecodeError, TypeError):
                            pass
                        break
            written = agent_build_notebook(
                str(package_id),
                out_dir,
                profile=profile,
                report=report,
                input_overrides=scen.get("input_overrides") or None,
                measure_ids=list(ecms) if ecms else None,
                twin_run=twin,
                write_manifest=True,
            )
            st.session_state["studio_notebook_path"] = str(written["xlsx"])
            st.session_state["studio_notebook_manifest"] = str(written.get("manifest") or "")
            scen["notebook_package_id"] = str(package_id)
            scen["notebook_path"] = str(written["xlsx"])
            if ecms:
                scen["selected_ecm_ids"] = list(ecms)
            save_ecm_scenario(scen)
            for w in (validate_notebook(written["xlsx"]).get("warnings") or []):
                st.warning(w)
            st.success(f"Rebuilt from scenario → {written['xlsx']}")
        except Exception as exc:
            st.error(f"Rebuild from scenario failed: {exc}")

    xlsx = st.session_state.get("studio_notebook_path")
    scen_path = scen.get("notebook_path")
    if scen_path and Path(str(scen_path)).is_file() and (
        not xlsx or Path(str(xlsx)).stem != pick
    ):
        if Path(str(scen_path)).stem == pick:
            xlsx = str(scen_path)
            st.session_state["studio_notebook_path"] = xlsx
    if not xlsx or not Path(str(xlsx)).is_file() or Path(str(xlsx)).stem != pick:
        candidate = disk_stems.get(pick) or (out_dir / f"{pick}.xlsx")
        if Path(candidate).is_file():
            xlsx = str(candidate)
            st.session_state["studio_notebook_path"] = xlsx
        else:
            xlsx = None

    if refresh_clicked:
        if not xlsx or not Path(str(xlsx)).is_file():
            st.warning("No notebook on disk for this package yet — agent-build or Rebuild from scenario.")
        else:
            try:
                result = refresh_notebook_caches(xlsx)
                st.success(f"Caches refreshed: {result.get('updated_cells', 0)} cells")
            except Exception as exc:
                st.error(f"refresh-caches failed: {exc}")

    if not xlsx or not Path(str(xlsx)).is_file():
        st.info(
            f"No `{pick}.xlsx` under `{out_dir}` yet. "
            "Agent: `wattlab notebook agent-build --package … --out /data/reports/notebooks/` "
            "or use **Rebuild from scenario.json**."
        )
        st.caption(f"Scenario file → `{default_ecm_scenario_path()}`")
        return

    path = Path(str(xlsx))
    mode = st.radio(
        "Preview mode",
        options=["formulas", "values"],
        format_func=lambda k: "Formulas (Excel code)" if k == "formulas" else "Values (caches / static)",
        horizontal=True,
        key="ecm_notebook_preview_mode",
        help="Formulas = exact cell formula text. Values = numeric caches where Excel has not calc'd.",
    )
    tabs = st.tabs(["Inputs", "ESCO_Calcs", "Compare", "ROI_Capital"])
    for tab, sheet in zip(tabs, ("Inputs", "ESCO_Calcs", "Compare", "ROI_Capital")):
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
    st.caption(f"On disk: `{path}` · scenario → `{default_ecm_scenario_path()}`")


def render() -> None:
    st.header("ECMs — engineering notebooks")
    st.caption(
        "Studio is a **read-only mirror** of agent-written Excel under `reports/notebooks/`. "
        "No Easy Buttons / capital-plan / client DOCX / OpenFDD. "
        "Chat picks ECMs → agent writes `.xlsx` → refresh browser → download."
    )
    _render_mirror()
