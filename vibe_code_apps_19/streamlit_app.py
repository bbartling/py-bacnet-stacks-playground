"""Vibe Code App 19 — 50-rule pandas/Streamlit FDD demo."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

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
from app.role_map import apply_role_map, load_role_map, roles_from_columns_csv, save_role_map, suggest_roles  # noqa: E402
from app.rules import CANONICAL_RULE_COUNT, RULES, RULES_BY_ID, run_all, run_rule  # noqa: E402
from app.rules.runner import infer_equipment_kind  # noqa: E402

st.set_page_config(page_title="Vibe19 FDD Demo", layout="wide")
st.title("Vibe Code App 19 — 50-rule pandas FDD lab")
st.caption(
    "Educational Streamlit demo with the full Open-FDD **pandas cookbook** (50 rules). "
    "Production Rust/DataFusion engine: [Open-FDD](https://github.com/bbartling/open-fdd)."
)


@st.cache_data
def load_inventory(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}


def _init_state() -> None:
    cfg = AppConfig.load()
    for k, v in {
        "equipment_frames": {},
        "selected_equipment": None,
        "batch_results": [],
        "params": {},
        "engineer_notes": {},
        "role_map": load_role_map(cfg.role_map_path),
        "weather": None,
        "building_id": cfg.building_id,
        "data_root": str(cfg.data_root),
        "data_source": "BUILDING_100",
    }.items():
        st.session_state.setdefault(k, v)


def _sidebar_sliders(defaults_cfg: dict) -> dict:
    out = dict(st.session_state.params)
    st.sidebar.subheader("Rule tuning")
    rule_filter = st.sidebar.text_input("Filter rules", "")
    for rule in RULES:
        if rule_filter and rule_filter.upper() not in rule.id:
            continue
        block = defaults_cfg.get(rule.id, {})
        if not block:
            continue
        with st.sidebar.expander(f"{rule.id} — {rule.title[:40]}", expanded=False):
            rp = dict(out.get(rule.id, {}))
            for pname, meta in block.items():
                rp[pname] = st.slider(
                    meta.get("label", pname),
                    min_value=float(meta["min"]),
                    max_value=float(meta["max"]),
                    value=float(rp.get(pname, meta["default"])),
                    step=float(meta.get("step", 0.5)),
                    help=meta.get("help", ""),
                    key=f"s_{rule.id}_{pname}",
                )
            out[rule.id] = rp
    if st.sidebar.button("Reset sliders"):
        st.session_state.params = {}
        st.rerun()
    st.session_state.params = out
    return out


def _load_data(cfg: AppConfig) -> None:
    mode = st.sidebar.radio(
        "Data input",
        ["BUILDING_100 tree", "Local CSV folder", "Upload CSV", "SQLite", "DuckDB SELECT", "Parquet"],
    )
    frames: dict[str, pd.DataFrame] = {}
    weather = None
    source = mode
    if mode == "BUILDING_100 tree":
        root = st.sidebar.text_input("HVAC_DATA_ROOT", st.session_state.data_root)
        building = st.sidebar.text_input("Building ID", st.session_state.building_id)
        st.session_state.data_root, st.session_state.building_id = root, building
        frames = cached_building_tree(root, building)
        weather = cached_weather(root, cfg.weather_subdir)
        source = f"{root}/{building}"
    elif mode == "Local CSV folder":
        folder = st.sidebar.text_input("Folder", st.session_state.data_root)
        p = Path(folder)
        if p.is_dir():
            for eq in discover_equipment(p):
                from app.cache import cached_equipment_csv

                df = cached_equipment_csv(str(eq["history_path"]), str(eq["columns_path"]) if eq["columns_path"] else None)
                df.attrs["equipment_id"] = eq["equipment_id"]
                frames[eq["equipment_id"]] = df
            source = str(p)
    elif mode == "Upload CSV":
        up = st.sidebar.file_uploader("CSV", type=["csv"])
        eq = st.sidebar.text_input("Equipment ID", "UPLOAD_1")
        if up:
            df = cached_upload_bytes(up.name, up.getvalue())
            df.attrs["equipment_id"] = eq
            frames[eq] = df
            source = f"upload:{up.name}"
    elif mode == "SQLite":
        db, table = st.sidebar.text_input("SQLite path"), st.sidebar.text_input("Table", "history")
        if db and table:
            df = cached_sqlite(db, table)
            eq = st.sidebar.text_input("Equipment ID", "SQLITE_1", key="sqeq")
            df.attrs["equipment_id"] = eq
            frames[eq] = df
            source = f"sqlite:{db}/{table}"
    elif mode == "DuckDB SELECT":
        db = st.sidebar.text_input("DuckDB path")
        query = st.sidebar.text_area("Query", "SELECT * FROM history LIMIT 1000")
        if db and query.strip().lower().startswith("select"):
            df = cached_duckdb(db, query)
            eq = st.sidebar.text_input("Equipment ID", "DUCK_1", key="deq")
            df.attrs["equipment_id"] = eq
            frames[eq] = df
            source = f"duckdb:{db}"
    elif mode == "Parquet":
        pq = st.sidebar.text_input("Parquet path")
        if pq:
            df = cached_parquet(pq)
            eq = st.sidebar.text_input("Equipment ID", "PQ_1", key="peq")
            df.attrs["equipment_id"] = eq
            frames[eq] = df
            source = f"parquet:{pq}"

    if frames:
        st.session_state.equipment_frames = frames
        st.session_state.weather = weather
        st.session_state.data_source = source
        if st.session_state.selected_equipment not in frames:
            st.session_state.selected_equipment = sorted(frames)[0]

    for sec in ("Overview", "Trends", "Fault Results"):
        st.session_state.engineer_notes[sec] = st.sidebar.text_area(sec, st.session_state.engineer_notes.get(sec, ""), height=70, key=f"n_{sec}")


def main() -> None:
    _init_state()
    cfg = AppConfig.load()
    defaults_cfg = cached_rule_defaults(str(cfg.rule_defaults_path))
    inventory = load_inventory(str(APP_ROOT / "configs" / "rule_inventory.yaml"))
    _load_data(cfg)
    _sidebar_sliders(defaults_cfg)

    frames = st.session_state.equipment_frames
    if not frames:
        st.info("Set HVAC_DATA_ROOT or choose another input mode.")
        return

    eq_ids = sorted(frames)
    selected = st.selectbox("Equipment", eq_ids, index=eq_ids.index(st.session_state.selected_equipment))
    st.session_state.selected_equipment = selected
    raw_df = frames[selected]
    mapped = apply_role_map(raw_df, selected, st.session_state.role_map)
    mapped.attrs["equipment_id"] = selected
    poll = float(raw_df.attrs.get("poll_seconds") or infer_poll_seconds(raw_df))
    kind = infer_equipment_kind(selected)

    tabs = st.tabs(
        ["Overview", "Data Input", "Role Mapping", "Rule Inventory", "Rule Tuning", "Fault Results", "Trends / Debug", "Export"]
    )

    with tabs[0]:
        st.subheader("Overview")
        if st.session_state.engineer_notes.get("Overview"):
            st.markdown(st.session_state.engineer_notes["Overview"])
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Equipment", len(frames))
        c2.metric("Canonical rules", CANONICAL_RULE_COUNT)
        c3.metric("Rows", len(raw_df))
        c4.metric("Poll (s)", f"{poll:.0f}")
        c5.metric("Kind", kind)
        st.write(f"**Source:** `{st.session_state.data_source}`")
        if isinstance(raw_df.index, pd.DatetimeIndex) and len(raw_df.index):
            st.write(f"**Range:** {raw_df.index.min()} → {raw_df.index.max()}")

    with tabs[1]:
        st.subheader("Data Input")
        st.write("Mode and paths are configured in the sidebar.")
        issues = validate_dataframe(raw_df)
        st.write("Validation:", issues or "OK")
        st.dataframe(raw_df.head(100), use_container_width=True)

    with tabs[2]:
        st.subheader("Role Mapping")
        inferred = {**suggest_roles(raw_df), **roles_from_columns_csv(Path(raw_df.attrs.get("columns_path")) if raw_df.attrs.get("columns_path") else None)}
        edit = dict(st.session_state.role_map.get(selected, {}))
        for role in sorted(set(list(inferred.keys()) + list(edit.keys()) + ["zone_t", "sat", "sat_sp", "oa_t", "fan_cmd"])):
            opts = [""] + list(raw_df.columns)
            edit[role] = st.selectbox(role, opts, index=opts.index(edit.get(role, inferred.get(role, ""))) if edit.get(role, inferred.get(role, "")) in opts else 0, key=f"r_{selected}_{role}")
        edit = {k: v for k, v in edit.items() if v}
        st.session_state.role_map[selected] = edit
        if st.button("Save role map"):
            save_role_map(cfg.role_map_path, st.session_state.role_map)
            st.success("Saved")

    with tabs[3]:
        st.subheader("Rule Inventory")
        results = st.session_state.batch_results
        if results:
            df_sum = results_summary_table(results)
            st.metric("Implemented", CANONICAL_RULE_COUNT)
            st.metric("PASS", int((df_sum["status"] == "PASS").sum()))
            st.metric("FAULT", int((df_sum["status"] == "FAULT").sum()))
            st.metric("SKIPPED", int((df_sum["status"] == "SKIPPED").sum()))
            st.metric("ERROR", int((df_sum["status"] == "ERROR").sum()))
        inv_rows = inventory.get("rules", [])
        st.dataframe(pd.DataFrame(inv_rows)[["rule_id", "family", "title", "required_roles", "implemented", "test_coverage"]], use_container_width=True, height=400)

    with tabs[4]:
        st.subheader("Rule Tuning")
        if st.button("Run all 50 rules — selected equipment", type="primary"):
            st.session_state.batch_results = run_all(mapped, st.session_state.params, poll, st.session_state.weather)
        if st.button("Run all 50 rules — ALL equipment (batch)"):
            batch = []
            for eq, rdf in frames.items():
                m = apply_role_map(rdf, eq, st.session_state.role_map)
                m.attrs["equipment_id"] = eq
                ps = float(rdf.attrs.get("poll_seconds") or infer_poll_seconds(rdf))
                batch.extend(run_all(m, st.session_state.params, ps, st.session_state.weather))
            st.session_state.batch_results = batch
            st.success(f"Ran {len(batch)} evaluations")

    with tabs[5]:
        st.subheader("Fault Results")
        results = st.session_state.batch_results
        if not results:
            st.info("Run rules from Rule Tuning tab.")
        else:
            summary = results_summary_table(results)
            st.dataframe(summary.sort_values(["status", "fault_hours"], ascending=[True, False]), use_container_width=True)
            faulted = summary[summary["status"] == "FAULT"].sort_values("fault_hours", ascending=False).head(20)
            if not faulted.empty:
                st.write("**Top faults**")
                st.dataframe(faulted, use_container_width=True)
            skipped = summary[summary["status"] == "SKIPPED"]
            if not skipped.empty:
                with st.expander(f"Skipped ({len(skipped)})"):
                    st.dataframe(skipped[["rule_id", "equipment_id", "missing_roles", "notes"]], use_container_width=True)

    with tabs[6]:
        st.subheader("Trends / Debug")
        rule_pick = st.selectbox("Rule", [r.id for r in RULES])
        if st.button("Run single rule for charts"):
            st.session_state.single = run_rule(rule_pick, mapped, st.session_state.params.get(rule_pick, {}), poll, st.session_state.weather)
        if hasattr(st.session_state, "single") and st.session_state.single:
            r = st.session_state.single
            st.write(r.notes)
            fig = rule_result_chart(mapped, r)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            if r.confirmed_fault is not None:
                st.line_chart(r.confirmed_fault.astype(int))

    with tabs[7]:
        st.subheader("Export")
        results = st.session_state.batch_results
        if results:
            summary = results_summary_table(results)
            st.download_button("Summary CSV", to_csv_bytes(summary), "fdd_summary.csv")
            md = markdown_report(
                building_id=st.session_state.building_id,
                data_source=st.session_state.data_source,
                results=results,
                engineer_notes=st.session_state.engineer_notes,
                params_snapshot={rid: p for rid, p in st.session_state.params.items()},
            )
            st.download_button("Markdown report", md.encode(), "report.md")
            st.download_button("HTML report", html_report(md).encode(), "report.html")


if __name__ == "__main__":
    main()
