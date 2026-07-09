"""Vibe Code App 19 — educational pandas/Streamlit FDD demo."""

from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

APP_ROOT = Path(__file__).resolve().parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.cache import (  # noqa: E402
    cached_building_tree,
    cached_duckdb,
    cached_parquet,
    cached_rule_defaults,
    cached_sqlite,
    cached_upload_bytes,
    cached_weather,
)
from app.charts import rule_result_chart  # noqa: E402
from app.config import AppConfig  # noqa: E402
from app.data_loader import discover_equipment, infer_poll_seconds, validate_dataframe  # noqa: E402
from app.reports import debug_frame, html_report, markdown_report, results_summary_table, to_csv_bytes  # noqa: E402
from app.role_map import (  # noqa: E402
    apply_role_map,
    load_role_map,
    roles_from_columns_csv,
    save_role_map,
    suggest_roles,
    validate_required_roles,
)
from app.rules import RULES, RULES_BY_ID, run_all, run_rule  # noqa: E402

st.set_page_config(page_title="Vibe19 FDD Demo", layout="wide")
st.title("Vibe Code App 19 — pandas FDD lab")
st.caption(
    "Educational Streamlit demo for CSV historian data. "
    "Production Rust/DataFusion engine lives in [Open-FDD](https://github.com/bbartling/open-fdd)."
)


def _init_state() -> None:
    defaults = {
        "data_source": "BUILDING_100",
        "equipment_frames": {},
        "selected_equipment": None,
        "rule_results": [],
        "params": {},
        "engineer_notes": {},
        "role_map": {},
        "weather": None,
        "building_id": AppConfig.load().building_id,
        "data_root": str(AppConfig.load().data_root),
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


def _sidebar_sliders(defaults_cfg: dict, params: dict) -> dict:
    out = dict(params)
    st.sidebar.subheader("Rule tuning")
    for spec in RULES:
        block = defaults_cfg.get(spec.config_key, {})
        if not block:
            continue
        with st.sidebar.expander(spec.label, expanded=False):
            rule_params = dict(out.get(spec.rule_id, {}))
            for pname, meta in block.items():
                if pname == "confirm_minutes":
                    continue
                rule_params[pname] = st.slider(
                    f"{pname}",
                    min_value=float(meta["min"]),
                    max_value=float(meta["max"]),
                    value=float(rule_params.get(pname, meta["default"])),
                    step=float(meta.get("step", 0.5)),
                    key=f"slider_{spec.rule_id}_{pname}",
                )
            if "confirm_minutes" in block:
                cm = block["confirm_minutes"]
                rule_params["_confirm_minutes"] = st.slider(
                    "confirm_minutes",
                    min_value=float(cm["min"]),
                    max_value=float(cm["max"]),
                    value=float(rule_params.get("_confirm_minutes", cm["default"])),
                    step=float(cm.get("step", 5)),
                    key=f"slider_{spec.rule_id}_confirm",
                )
            out[spec.rule_id] = rule_params
    if st.sidebar.button("Reset sliders to defaults"):
        st.session_state.params = {}
        st.rerun()
    return out


def _load_data(cfg: AppConfig) -> None:
    mode = st.sidebar.radio(
        "Data input",
        ["BUILDING_100 tree", "Local CSV folder", "Upload CSV", "SQLite", "DuckDB SELECT", "Parquet"],
        key="input_mode",
    )
    frames: dict[str, pd.DataFrame] = {}
    weather = None
    source_label = mode

    if mode == "BUILDING_100 tree":
        root = st.sidebar.text_input("HVAC_DATA_ROOT", value=st.session_state.data_root)
        building = st.sidebar.text_input("Building ID", value=st.session_state.building_id)
        st.session_state.data_root = root
        st.session_state.building_id = building
        try:
            frames = cached_building_tree(root, building)
            weather = cached_weather(root, cfg.weather_subdir)
            source_label = f"{root}/{building}"
        except Exception as exc:
            st.sidebar.error(f"Load failed: {exc}")
    elif mode == "Local CSV folder":
        folder = st.sidebar.text_input("Folder path", value=st.session_state.data_root)
        p = Path(folder)
        if p.is_dir():
            for eq in discover_equipment(p):
                df = cached_building_tree(str(p.parent), p.name).get(eq["equipment_id"])
                if df is None:
                    from app.cache import cached_equipment_csv

                    df = cached_equipment_csv(str(eq["history_path"]), str(eq["columns_path"]) if eq["columns_path"] else None)
                    df.attrs["equipment_id"] = eq["equipment_id"]
                frames[eq["equipment_id"]] = df
            source_label = str(p)
    elif mode == "Upload CSV":
        up = st.sidebar.file_uploader("CSV file", type=["csv"])
        eq_id = st.sidebar.text_input("Equipment ID", value="UPLOAD_1")
        if up is not None:
            df = cached_upload_bytes(up.name, up.getvalue())
            df.attrs["equipment_id"] = eq_id
            frames[eq_id] = df
            source_label = f"upload:{up.name}"
    elif mode == "SQLite":
        db = st.sidebar.text_input("SQLite path", value="")
        table = st.sidebar.text_input("Table name", value="history")
        if db and table:
            df = cached_sqlite(db, table)
            eq_id = st.sidebar.text_input("Equipment ID", value="SQLITE_1", key="sqlite_eq")
            df.attrs["equipment_id"] = eq_id
            frames[eq_id] = df
            source_label = f"sqlite:{db}/{table}"
    elif mode == "DuckDB SELECT":
        db = st.sidebar.text_input("DuckDB path", value="")
        query = st.sidebar.text_area("SELECT query", value="SELECT * FROM history LIMIT 1000")
        if db and query.strip().lower().startswith("select"):
            df = cached_duckdb(db, query)
            eq_id = st.sidebar.text_input("Equipment ID", value="DUCK_1", key="duck_eq")
            df.attrs["equipment_id"] = eq_id
            frames[eq_id] = df
            source_label = f"duckdb:{db}"
    elif mode == "Parquet":
        pq = st.sidebar.text_input("Parquet path", value="")
        if pq:
            df = cached_parquet(pq)
            eq_id = st.sidebar.text_input("Equipment ID", value="PARQUET_1", key="pq_eq")
            df.attrs["equipment_id"] = eq_id
            frames[eq_id] = df
            source_label = f"parquet:{pq}"

    if frames:
        st.session_state.equipment_frames = frames
        st.session_state.weather = weather
        st.session_state.data_source = source_label
        if st.session_state.selected_equipment not in frames:
            st.session_state.selected_equipment = sorted(frames)[0]

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Engineer chart notes** (saved in session)")
    for section in ("Overview", "Trends", "Fault Results"):
        st.session_state.engineer_notes[section] = st.sidebar.text_area(
            section, value=st.session_state.engineer_notes.get(section, ""), height=80, key=f"note_{section}"
        )


def main() -> None:
    _init_state()
    cfg = AppConfig.load()
    defaults_cfg = cached_rule_defaults(str(cfg.rule_defaults_path))
    role_map = load_role_map(cfg.role_map_path)
    st.session_state.role_map = role_map

    _load_data(cfg)
    st.session_state.params = _sidebar_sliders(defaults_cfg, st.session_state.params)

    frames: dict[str, pd.DataFrame] = st.session_state.equipment_frames
    if not frames:
        st.info("Set **HVAC_DATA_ROOT** in `.env` or choose another input mode in the sidebar.")
        st.code("HVAC_DATA_ROOT=C:\\path\\to\\hvac_systems_CLEANED\nstreamlit run streamlit_app.py", language="text")
        return

    eq_ids = sorted(frames)
    selected = st.selectbox("Equipment", eq_ids, index=eq_ids.index(st.session_state.selected_equipment))
    st.session_state.selected_equipment = selected
    raw_df = frames[selected]
    mapped_df = apply_role_map(raw_df, selected, st.session_state.role_map)
    mapped_df.attrs["equipment_id"] = selected
    poll = float(raw_df.attrs.get("poll_seconds") or infer_poll_seconds(raw_df))

    tabs = st.tabs(
        ["Overview", "Data Preview", "Role Mapping", "Rule Tuning", "Fault Results", "Trends", "Export"]
    )

    with tabs[0]:
        st.subheader("Overview")
        if st.session_state.engineer_notes.get("Overview"):
            st.markdown(st.session_state.engineer_notes["Overview"])
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Equipment", len(frames))
        c2.metric("Rows", len(raw_df))
        c3.metric("Poll (s)", f"{poll:.0f}")
        if isinstance(raw_df.index, pd.DatetimeIndex) and len(raw_df.index):
            c4.metric("Date range", f"{raw_df.index.min().date()} → {raw_df.index.max().date()}")
        st.write(f"**Data source:** `{st.session_state.data_source}`")
        issues = validate_dataframe(raw_df)
        if issues:
            st.warning("Data issues: " + "; ".join(issues))
        missing_all = []
        for spec in RULES:
            missing_all.extend(validate_required_roles(selected, mapped_df, st.session_state.role_map, spec.required_roles))
        if missing_all:
            st.warning(f"Missing roles for selected equipment: {', '.join(sorted(set(missing_all)))}")

    with tabs[1]:
        st.subheader("Data Preview")
        st.dataframe(raw_df.head(200), use_container_width=True)
        st.write("**Columns:**", list(raw_df.columns))
        if isinstance(raw_df.index, pd.DatetimeIndex):
            dup = int(raw_df.index.duplicated().sum())
            st.write(f"Timestamp health: {len(raw_df)} rows, {dup} duplicates")

    with tabs[2]:
        st.subheader("Role Mapping")
        inferred = suggest_roles(raw_df)
        cols_path = raw_df.attrs.get("columns_path")
        from_cols = roles_from_columns_csv(Path(cols_path)) if cols_path else {}
        merged = {**inferred, **from_cols, **st.session_state.role_map.get(selected, {})}
        st.write("Suggested / current roles for", selected)
        edit: dict[str, str] = {}
        for role in sorted(set(list(merged.keys()) + ["zone_t", "sat", "sat_sp", "oa_t", "fan_cmd", "oa_damper_pct", "clg_valve_pct", "mat", "rat"])):
            options = [""] + list(raw_df.columns)
            default_col = merged.get(role, "")
            idx = options.index(default_col) if default_col in options else 0
            edit[role] = st.selectbox(role, options, index=idx, key=f"role_{selected}_{role}")
        edit = {k: v for k, v in edit.items() if v}
        st.session_state.role_map[selected] = edit
        c1, c2 = st.columns(2)
        if c1.button("Save role map YAML"):
            save_role_map(cfg.role_map_path, st.session_state.role_map)
            st.success(f"Saved {cfg.role_map_path}")
        if c2.button("Reset to file defaults"):
            st.session_state.role_map = load_role_map(cfg.role_map_path)
            st.rerun()
        for spec in RULES:
            miss = validate_required_roles(selected, apply_role_map(raw_df, selected, st.session_state.role_map), st.session_state.role_map, spec.required_roles)
            if miss:
                st.warning(f"{spec.rule_id} missing: {', '.join(miss)}")

    with tabs[3]:
        st.subheader("Rule Tuning")
        st.json(st.session_state.params)
        rule_pick = st.multiselect("Rules to run", [r.rule_id for r in RULES], default=[r.rule_id for r in RULES])
        if st.button("Run selected rules", type="primary"):
            results = []
            df = apply_role_map(raw_df, selected, st.session_state.role_map)
            df.attrs["equipment_id"] = selected
            for rid in rule_pick:
                spec = RULES_BY_ID[rid]
                miss = validate_required_roles(selected, df, st.session_state.role_map, spec.required_roles)
                if miss and spec.rule_id != "OAT-METEO":
                    continue
                p = dict(st.session_state.params.get(rid, {}))
                results.append(run_rule(spec, df, p, poll, st.session_state.weather))
            st.session_state.rule_results = results
        if st.button("Run all equipment (summary only)"):
            all_results = []
            for eq, rdf in frames.items():
                df = apply_role_map(rdf, eq, st.session_state.role_map)
                df.attrs["equipment_id"] = eq
                ps = float(rdf.attrs.get("poll_seconds") or infer_poll_seconds(rdf))
                all_results.extend(run_all(df, st.session_state.params, ps, st.session_state.weather))
            st.session_state.rule_results = all_results

    with tabs[4]:
        st.subheader("Fault Results")
        if st.session_state.engineer_notes.get("Fault Results"):
            st.markdown(st.session_state.engineer_notes["Fault Results"])
        results = st.session_state.rule_results
        if not results:
            st.info("Run rules from the Rule Tuning tab.")
        else:
            summary = results_summary_table(results)
            st.dataframe(summary.sort_values("fault_hours", ascending=False), use_container_width=True)
            faulted = summary[summary["fault_hours"] > 0].sort_values("fault_pct", ascending=False).head(10)
            if not faulted.empty:
                st.write("**Top faulted**")
                st.dataframe(faulted, use_container_width=True)

    with tabs[5]:
        st.subheader("Trends")
        if st.session_state.engineer_notes.get("Trends"):
            st.markdown(st.session_state.engineer_notes["Trends"])
        df = apply_role_map(raw_df, selected, st.session_state.role_map)
        plot_cols = st.multiselect("Points", [c for c in df.columns if c != "timestamp"], default=[c for c in ("zone_t", "sat", "oa_t") if c in df.columns])
        overlay = None
        for r in st.session_state.rule_results:
            if r.equipment_id == selected:
                overlay = r.confirmed_fault
                break
        if plot_cols:
            import plotly.graph_objects as go

            fig = go.Figure()
            for col in plot_cols:
                fig.add_trace(go.Scatter(x=df.index, y=df[col], name=col))
            if overlay is not None:
                m = overlay.reindex(df.index).fillna(False).astype(bool)
                fig.add_trace(go.Scatter(x=m.index[m], y=df.loc[m, plot_cols[0]], mode="markers", name="fault", marker=dict(color="red", size=5)))
            fig.update_layout(height=450, title=f"{selected} trends")
            st.plotly_chart(fig, use_container_width=True)
        for r in st.session_state.rule_results:
            if r.equipment_id == selected:
                fig = rule_result_chart(df, r)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)

    with tabs[6]:
        st.subheader("Export")
        results = st.session_state.rule_results
        if results:
            summary = results_summary_table(results)
            st.download_button("Download summary CSV", to_csv_bytes(summary), "fdd_summary.csv", "text/csv")
            dbg = debug_frame(results[0])
            st.download_button("Download debug CSV (first result)", to_csv_bytes(dbg), "fdd_debug.csv", "text/csv")
            md = markdown_report(
                building_id=st.session_state.building_id,
                data_source=st.session_state.data_source,
                results=results,
                engineer_notes=st.session_state.engineer_notes,
                params_snapshot={k: v for d in st.session_state.params.values() for k, v in d.items()},
            )
            st.download_button("Download Markdown report", md.encode("utf-8"), "fdd_report.md", "text/markdown")
            st.download_button("Download HTML report", html_report(md).encode("utf-8"), "fdd_report.html", "text/html")
        else:
            st.info("Run rules first to enable export.")


if __name__ == "__main__":
    main()
