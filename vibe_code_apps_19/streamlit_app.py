"""Vibe Code App 19 — 50-rule pandas/Streamlit FDD demo."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

APP_ROOT = Path(__file__).resolve().parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.cache import (  # noqa: E402
    cached_building_folder,
    cached_rule_defaults,
    cached_weather,
)
from app.analytics import (  # noqa: E402
    PLANT_AIR,
    PLANT_BOILER,
    PLANT_CHILLER,
    dataset_time_span,
    mech_cooling_oat_bins,
    motor_run_hours_table,
    motor_run_hours_totals,
    motor_run_hours_weekly,
    sensor_fault_summary,
)
from app.charts import (  # noqa: E402
    mech_cooling_oat_histogram,
    motor_weekly_runtime_chart,
    plotly_config,
    rule_result_chart,
)
from app.config import AppConfig  # noqa: E402
from app.data_loader import infer_poll_seconds, list_building_candidates, validate_dataframe  # noqa: E402
from app.occupancy import DAYS, DAY_LABELS, OccupancySchedule, apply_schedule_occ_mode, occupied_hours_per_week  # noqa: E402
from app.ui_rcx_tab import render_rcx_plots_tab  # noqa: E402
from app.unit_system import c_to_f, f_to_c, units_map_for_system  # noqa: E402
from app.mapping_wizard import (  # noqa: E402
    DEFAULT_BUILDING_ID,
    DEFAULT_SITE_ID,
    equipment_context,
    flat_role_map_from_sites,
    load_site_mapping,
    save_site_mapping,
    upsert_equipment_roles,
    wrap_flat_role_map,
)
from app.reports import results_summary_table, to_csv_bytes  # noqa: E402
import importlib  # noqa: E402
from app import column_map_json as _column_map_json_mod  # noqa: E402
from app import role_map as _role_map_mod  # noqa: E402

# Streamlit keeps stale modules in memory across edits; force reload.
_column_map_json_mod = importlib.reload(_column_map_json_mod)
FAMILY_ORDER = _column_map_json_mod.FAMILY_ORDER
LLM_COLUMN_MAP_PROMPT = _column_map_json_mod.LLM_COLUMN_MAP_PROMPT
build_column_map_from_equipment_frames = _column_map_json_mod.build_column_map_from_equipment_frames
build_llm_prompt_for_frames = _column_map_json_mod.build_llm_prompt_for_frames
column_map_to_role_map = _column_map_json_mod.column_map_to_role_map
family_label = _column_map_json_mod.family_label
load_column_map_json = _column_map_json_mod.load_column_map_json
merge_column_map_into_role_map = _column_map_json_mod.merge_column_map_into_role_map
natural_key = _column_map_json_mod.natural_key
normalize_column_map = _column_map_json_mod.normalize_column_map
save_column_map_json = _column_map_json_mod.save_column_map_json
to_haystack_document = _column_map_json_mod.to_haystack_document
validate_column_map_against_frames = _column_map_json_mod.validate_column_map_against_frames

_role_map_mod = importlib.reload(_role_map_mod)
apply_role_map = _role_map_mod.apply_role_map
enrich_role_map_from_equipment = _role_map_mod.enrich_role_map_from_equipment
load_role_map = _role_map_mod.load_role_map
roles_from_columns_csv = _role_map_mod.roles_from_columns_csv
save_role_map = _role_map_mod.save_role_map
suggest_roles = _role_map_mod.suggest_roles
from app.rules import CANONICAL_RULE_COUNT, RULES, RULES_BY_ID, run_rule  # noqa: E402
from app.rules.operational_gate import RULE_GATES  # noqa: E402
from app.rules.runner import infer_equipment_kind  # noqa: E402
from app.site_model import Building, Site, equipment_type_from_id  # noqa: E402

try:
    from shared.branding import APP_TITLE
except ImportError:  # pragma: no cover
    APP_TITLE = "Open FDD Vibe Coder"

st.set_page_config(page_title=APP_TITLE, layout="wide")

_AGENTS_MD_URL = (
    "https://github.com/bbartling/py-bacnet-stacks-playground/blob/develop/"
    "vibe_code_apps_19/AGENTS.md"
)
_OPENFDD_DOCS_URL = "https://bbartling.github.io/open-fdd/"
_OPENFDD_REPO_URL = "https://github.com/bbartling/open-fdd"
_HERO_IMG = APP_ROOT / "assets" / "image_new_chiller.png"


def _render_app_hero() -> None:
    """Brand header: title → subtitle → compact logo → how-it-works."""
    st.title(APP_TITLE)
    st.markdown(
        "Educational Streamlit + pandas lab for the Open-FDD 50-rule cookbook. "
        "CSVs stay as-is — you only map columns to roles."
    )
    if _HERO_IMG.is_file():
        # Narrower than full-bleed stretch so the logo sits under the brand, not above it
        _logo_l, _logo_m, _logo_r = st.columns([1, 2, 1])
        with _logo_m:
            st.image(str(_HERO_IMG), width="stretch")
    st.markdown(
        """
**How it works (2 pieces + run)**

1. **Data package** — Folder or `openfdd_package_v1` zip of historian CSVs  
2. **Data model** — JSON column→role map (Mapping tab) or `session_config.json` role_map in the zip  
3. **Run** — **Run Rules** → **Plots** / **RCx Plots**
        """.strip()
    )
    st.markdown(
        f"[AGENTS.md]({_AGENTS_MD_URL}) · "
        f"[Open-FDD docs]({_OPENFDD_DOCS_URL}) · "
        f"[Open-FDD repo]({_OPENFDD_REPO_URL})"
    )


_render_app_hero()


def _empty_state_directions() -> None:
    st.info(
        "**Start here:** sidebar → **Folder** (local tree) or **Zip package** → load data. "
        "Then **Data & Mapping** for the JSON data model (or rely on zip `session_config` role_map). "
        "Finally **Run Rules** → **Plots** / **RCx**."
    )
    st.markdown(
        f"Agent brief: [AGENTS.md]({_AGENTS_MD_URL}) · "
        f"Package contract: `docs/PACKAGE_SPEC.md` · "
        f"[Open-FDD docs]({_OPENFDD_DOCS_URL})"
    )


@st.cache_data
def load_inventory(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}


def _init_state() -> None:
    cfg = AppConfig.load()
    if "site_mapping" not in st.session_state:
        st.session_state.site_mapping = load_site_mapping(cfg.role_map_path)
    demo_building = cfg.data_root / cfg.building_id
    if demo_building.is_dir():
        default_folder = str(demo_building)
    elif cfg.data_root.is_dir():
        default_folder = str(cfg.data_root)
    else:
        default_folder = ""
    for k, v in {
        "equipment_frames": {},
        "selected_equipment": None,
        "batch_results": [],
        "params": {},
        "engineer_notes": {},
        "role_map": flat_role_map_from_sites(st.session_state.site_mapping),
        "weather": None,
        "building_id": "",
        "site_id": DEFAULT_SITE_ID,
        "building_folder": "" if (cfg.is_cloud or not cfg.allow_server_paths) else default_folder,
        "data_root": str(cfg.data_root),
        "data_source": "",
        "column_map": {},
        "column_map_path": "",
        "require_operational_gates": True,
        "unit_system": "imperial",
        "prefer_web_oat": True,
        "chw_leave_max_f": 48.0,
        "include_ahu_chw_valve": False,  # hard-coded; never offer in UI
        "occupancy_schedule": OccupancySchedule().to_dict(),
        "apply_occupancy_calendar": True,  # always on; Overview calendar → occ_mode
        "zone_lo_f": 68.0,
        "zone_hi_f": 76.0,
        "upload_workdir": None,
        "package_report": None,
        "zip_uploader_key": 0,
        "fault_settings_source": "defaults",
        "session_config_source": "",
        "bootstrap_applied": False,
        "bootstrap_status": "",
    }.items():
        st.session_state.setdefault(k, v)


def _apply_agent_bootstrap_once() -> None:
    """Load ``VIBE19_BOOTSTRAP`` / ``.last_agent_session.json`` into this browser session once."""
    if st.session_state.get("bootstrap_applied"):
        return
    if st.session_state.get("equipment_frames"):
        # User already has data — don't clobber
        st.session_state.bootstrap_applied = True
        return
    try:
        from app.bootstrap import read_bootstrap
        from app.package_io import PackageError, SessionConfig, apply_session_config, load_package_zip
    except Exception as exc:  # pragma: no cover
        st.session_state.bootstrap_status = f"bootstrap import failed: {exc}"
        st.session_state.bootstrap_applied = True
        return

    try:
        boot = read_bootstrap()
    except Exception as exc:
        st.session_state.bootstrap_status = f"bootstrap read failed: {exc}"
        st.session_state.bootstrap_applied = True
        return
    if not boot:
        st.session_state.bootstrap_applied = True
        return

    pkg = boot.get("package_path")
    folder = boot.get("building_folder")
    try:
        if pkg and Path(str(pkg)).is_file():
            result = load_package_zip(Path(str(pkg)).read_bytes())
            # Keep a stable source label for the UI
            result.report["bootstrap_package"] = str(pkg)
            _commit_package_result(result)
            st.session_state.data_source = f"bootstrap:{Path(str(pkg)).name}"
        elif folder and Path(str(folder)).is_dir():
            from app.cache import cached_building_folder, cached_weather

            chosen = Path(str(folder))
            frames = cached_building_folder(str(chosen.resolve()))
            weather = None
            try:
                weather = cached_weather(str(chosen.parent), "weather")
            except Exception:
                weather = None
            _commit_frames(
                frames,
                site_id=st.session_state.site_id or DEFAULT_SITE_ID,
                building_id=chosen.name,
                source=f"bootstrap:{chosen.name}",
                weather=weather,
            )
            st.session_state.building_folder = str(chosen)
            st.session_state.data_input_mode = "Folder"
        else:
            # Missing host paths (typical Docker) — stay on Zip; do not prefill dead Folder paths
            st.session_state.building_folder = ""
            if st.session_state.get("data_input_mode") == "Folder":
                st.session_state.data_input_mode = "Zip package"
            st.session_state.bootstrap_status = (
                "Bootstrap path not on this host — upload a zip package (or mount data + APP_MODE=local)."
            )
            st.session_state.bootstrap_applied = True
            return

        # Overlay dialed-in session / fault settings from agent export
        sess = boot.get("session_config") or {}
        fs_path = boot.get("fault_settings_path")
        if fs_path and Path(str(fs_path)).is_file():
            raw = json.loads(Path(str(fs_path)).read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                params = dict(st.session_state.get("params") or {})
                for rid, p in raw.items():
                    if isinstance(p, dict):
                        params[str(rid)] = {**params.get(str(rid), {}), **p}
                st.session_state.params = params
                st.session_state.fault_settings_source = f"bootstrap:{Path(str(fs_path)).name}"
                sess = {**sess, "params": params}
        if sess:
            cfg_obj = SessionConfig.model_validate(
                {**sess, "schema_version": sess.get("schema_version") or "openfdd_session_v1"}
            )
            frames = st.session_state.get("equipment_frames") or {}
            for w in apply_session_config(cfg_obj, equipment_ids=set(frames)):
                st.warning(w)
            st.session_state.session_config_source = "bootstrap"

        cm_path = boot.get("column_map_path")
        if cm_path and Path(str(cm_path)).is_file():
            data = load_column_map_json(str(cm_path))
            _apply_column_map_json(data)
            st.session_state.column_map_path = str(cm_path)

        if boot.get("auto_run_rules") and st.session_state.get("equipment_frames"):
            import os as _os

            if (_os.environ.get("VIBE19_BOOTSTRAP_SKIP_RULES") or "").strip() in {"1", "true", "yes"}:
                st.session_state.bootstrap_status = (
                    "Loaded bootstrap (data + settings); rules skipped (VIBE19_BOOTSTRAP_SKIP_RULES)"
                )
            else:
                frames = st.session_state.equipment_frames
                st.session_state.batch_results = _run_rule_list(sorted(frames), RULES, frames)
                st.session_state.bootstrap_status = (
                    f"Loaded bootstrap + ran {len(st.session_state.batch_results)} rule evaluations"
                )
        else:
            st.session_state.bootstrap_status = "Loaded bootstrap (data + settings); run rules when ready"
    except PackageError as exc:
        st.session_state.bootstrap_status = f"bootstrap package error: {exc}"
    except Exception as exc:
        st.session_state.bootstrap_status = f"bootstrap failed: {exc}"
    finally:
        st.session_state.bootstrap_applied = True


def _clear_uploaded_session() -> None:
    """Wipe temp package dir + session data derived from an upload."""
    from app.package_io import wipe_workdir

    wipe_workdir(st.session_state.get("upload_workdir"))
    st.session_state.upload_workdir = None
    st.session_state.package_report = None
    st.session_state.equipment_frames = {}
    st.session_state.weather = None
    st.session_state.batch_results = []
    st.session_state.selected_equipment = None
    st.session_state.data_source = ""
    st.session_state.building_id = ""
    # Rotate uploader widget so Streamlit drops cached file bytes
    st.session_state.zip_uploader_key = int(st.session_state.get("zip_uploader_key", 0)) + 1


def _session_config_payload() -> dict:
    """Build ``openfdd_session_v1`` from current session_state (Cloud-safe export)."""
    from app.agent_api import make_session_config

    return make_session_config(
        st.session_state.get("role_map") or {},
        st.session_state.get("params") or {},
        unit_system=st.session_state.get("unit_system", "imperial"),
        prefer_web_oat=bool(st.session_state.get("prefer_web_oat", True)),
        chw_leave_max_f=float(st.session_state.get("chw_leave_max_f", 48.0)),
        include_ahu_chw_valve=False,  # never export legacy valve→mech-cooling path
    )


def _apply_session_config_bytes(raw: bytes, *, source_label: str) -> list[str]:
    """Validate + apply session_config JSON bytes into session_state. Returns warnings."""
    from app.package_io import SessionConfig, apply_session_config

    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("session_config JSON must be an object")
    if not data.get("schema_version"):
        data = {**data, "schema_version": "openfdd_session_v1"}
    cfg_obj = SessionConfig.model_validate(data)
    frames = st.session_state.get("equipment_frames") or {}
    warnings = apply_session_config(cfg_obj, equipment_ids=set(frames))
    st.session_state.session_config_source = source_label
    if cfg_obj.params:
        st.session_state.fault_settings_source = f"session:{source_label}"
    return warnings


def _render_session_config_io(*, key_prefix: str) -> None:
    """Download / upload tuned session_config (+ distinct fault_settings) — no server path."""
    st.caption(
        f"Active fault settings: `{st.session_state.get('fault_settings_source') or 'defaults'}`"
    )
    if st.session_state.get("session_config_source"):
        st.caption(f"Session config: `{st.session_state.session_config_source}`")

    try:
        session_payload = _session_config_payload()
    except Exception as exc:
        st.warning(f"Session config export unavailable: {exc}")
        session_payload = {
            "schema_version": "openfdd_session_v1",
            "unit_system": st.session_state.get("unit_system", "imperial"),
            "prefer_web_oat": bool(st.session_state.get("prefer_web_oat", True)),
            "role_map": st.session_state.get("role_map") or {},
            "params": st.session_state.get("params") or {},
        }

    st.download_button(
        "Download session config",
        data=json.dumps(session_payload, indent=2).encode("utf-8"),
        file_name="session_config.json",
        mime="application/json",
        key=f"{key_prefix}_dl_session_config",
        help="openfdd_session_v1: units, prefer_web_oat, role_map, params, plant toggles.",
    )
    fault_json = json.dumps(st.session_state.get("params") or {}, indent=2)
    st.download_button(
        "Download fault settings",
        data=fault_json.encode("utf-8"),
        file_name="fault_settings.json",
        mime="application/json",
        key=f"{key_prefix}_dl_fault_settings",
        help="rule_id → params only (subset of session_config.params).",
    )

    up_sess = st.file_uploader(
        "Upload session config",
        type=["json"],
        key=f"{key_prefix}_upload_session_config",
        help="Restore params + role_map into this browser session (Cloud-safe).",
    )
    if up_sess is not None and st.button(
        "Apply uploaded session config", key=f"{key_prefix}_apply_session_upload"
    ):
        try:
            warnings = _apply_session_config_bytes(
                up_sess.getvalue(), source_label=f"upload:{up_sess.name}"
            )
            for w in warnings:
                st.warning(w)
            st.success("Session config applied — re-run rules to refresh results.")
            st.rerun()
        except Exception as exc:
            st.error(f"Session config upload failed: {exc}")

    up_fault = st.file_uploader(
        "Upload fault settings",
        type=["json"],
        key=f"{key_prefix}_upload_fault_settings",
    )
    if up_fault is not None and st.button(
        "Apply uploaded fault settings", key=f"{key_prefix}_apply_fault_upload"
    ):
        try:
            raw = json.loads(up_fault.getvalue().decode("utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("JSON must be an object of rule_id → params")
            params = dict(st.session_state.get("params") or {})
            for rid, p in raw.items():
                if isinstance(p, dict):
                    params[str(rid)] = {**params.get(str(rid), {}), **p}
            st.session_state.params = params
            st.session_state.fault_settings_source = f"upload:{up_fault.name}"
            st.success("Fault settings applied — re-run rules to refresh results.")
            st.rerun()
        except Exception as exc:
            st.error(f"Fault settings upload failed: {exc}")


def _sync_role_map_from_sites() -> None:
    st.session_state.role_map = flat_role_map_from_sites(st.session_state.site_mapping)


def _apply_column_map_json(data: dict) -> None:
    """Merge JSON column map into session role_map + site mapping."""
    normalized = normalize_column_map(data)
    st.session_state.column_map = normalized
    st.session_state.role_map = merge_column_map_into_role_map(
        st.session_state.role_map, normalized, prefer_json=True
    )
    for eq_id, roles in column_map_to_role_map(normalized).items():
        upsert_equipment_roles(
            st.session_state.site_mapping,
            site_id=st.session_state.site_id,
            building_id=st.session_state.building_id,
            equipment_id=eq_id,
            equipment_type=equipment_type_from_id(eq_id),
            roles=roles,
        )
    _sync_role_map_from_sites()
    if st.session_state.equipment_frames:
        _attach_frames_meta(st.session_state.equipment_frames)


def _rules_by_family() -> dict[str, list]:
    buckets: dict[str, list] = {f: [] for f in FAMILY_ORDER}
    for rule in RULES:
        fam = rule.family if rule.family in buckets else "other"
        buckets[fam].append(rule)
    for fam in buckets:
        buckets[fam].sort(key=lambda r: natural_key(r.id))
    return buckets


def _results_by_family(summary: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if summary.empty:
        return {}
    out: dict[str, pd.DataFrame] = {}
    fam_lookup = {r.id: r.family for r in RULES}
    df = summary.copy()
    df["family"] = df["rule_id"].map(lambda rid: fam_lookup.get(rid, "other"))
    for fam in FAMILY_ORDER:
        part = df[df["family"] == fam].copy()
        if part.empty:
            continue
        part = part.loc[
            sorted(
                part.index,
                key=lambda i: (natural_key(str(part.at[i, "rule_id"])), str(part.at[i, "equipment_id"])),
            )
        ]
        out[fam] = part
    return out


def _attach_frames_meta(frames: dict[str, pd.DataFrame]) -> None:
    rm = st.session_state.role_map
    for eq_id, df in frames.items():
        sid, bid, etype = equipment_context(st.session_state.site_mapping, eq_id)
        df.attrs.setdefault("site_id", sid)
        df.attrs.setdefault("building_id", bid)
        df.attrs.setdefault("equipment_type", etype)
        df.attrs["_role_map"] = rm


_CONFIRM_META = {
    "label": "Fault confirm delay",
    "default": 5.0,
    "min": 0.0,
    "max": 60.0,
    "step": 1.0,
    "unit": "min",
    "help": "Minutes a raw fault must persist before it is confirmed. Default 5; 0 = confirm on first sample; max 60.",
}


@st.fragment
def _sidebar_sliders(defaults_cfg: dict) -> None:
    """Left-rail rule tuning. Fragment-isolated so slider moves do not re-run rules/plots."""
    out = dict(st.session_state.params)
    st.sidebar.subheader("Rule tuning")
    st.sidebar.caption(
        "Sliders only change thresholds. Rules update when you click **Run** (Run Rules tab) or **Rerun cat.**"
    )
    st.session_state.require_operational_gates = st.sidebar.checkbox(
        "Require operational proof (fan/pump status)",
        value=st.session_state.get("require_operational_gates", True),
        help=(
            "When checked, RUN rules only evaluate while fan/pump/compressor is proven on "
            "(status preferred over command). Off-period samples become SKIPPED_EQUIPMENT_OFF, not PASS."
        ),
        key="ops_gate_global",
    )
    fam_labels = [family_label(f) for f in FAMILY_ORDER if _rules_by_family().get(f)]
    fam_pick = st.sidebar.selectbox(
        "Category",
        ["(all)"] + fam_labels,
        key="tune_fam",
    )
    fam_lookup = {family_label(f): f for f in FAMILY_ORDER}
    allow_ids = None
    fam_key = None
    if fam_pick != "(all)":
        fam_key = fam_lookup[fam_pick]
        allow_ids = {r.id for r in _rules_by_family().get(fam_key, [])}

    for rule in RULES:
        if allow_ids is not None and rule.id not in allow_ids:
            continue
        block = dict(defaults_cfg.get(rule.id, {}))
        if "confirm_min" not in block:
            block["confirm_min"] = dict(_CONFIRM_META)
        gate = RULE_GATES.get(rule.id)
        if gate and gate.kind != "always":
            block.setdefault(
                "require_operational_gate",
                {
                    "label": "Require operational proof",
                    "default": 1.0,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 1.0,
                    "unit": "0/1",
                    "help": "1 = gate on for this rule (fan/pump proven). 0 = evaluate all samples.",
                },
            )
            block.setdefault(
                "startup_delay_min",
                {
                    "label": "Startup delay",
                    "default": gate.startup_delay_seconds / 60.0,
                    "min": 0.0,
                    "max": 30.0,
                    "step": 1.0,
                    "unit": "min",
                    "help": "Ignore samples until equipment has been proven on this long.",
                },
            )
        with st.sidebar.expander(f"{rule.id} — {rule.title[:36]}", expanded=False):
            rp = dict(out.get(rule.id, {}))
            # Fault confirm delay first, then gate toggles, then other params
            preferred = ["confirm_min", "require_operational_gate", "startup_delay_min"]
            ordered = [k for k in preferred if k in block] + [k for k in block if k not in preferred]
            for pname in ordered:
                meta = block[pname]
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

    c1, c2 = st.sidebar.columns(2)
    if c1.button("Reset", key="reset_tune"):
        st.session_state.params = {}
        st.rerun()
    st.session_state.params = out
    st.session_state["_sidebar_fam_key"] = fam_key
    if c2.button("Rerun cat.", key="rerun_cat_sidebar", help="Rerun the selected mechanical category on all equipment"):
        st.session_state["_pending_rerun_family"] = fam_key  # None = all
        st.rerun()


def _units_map() -> dict[str, str]:
    cm = st.session_state.get("column_map") or {}
    units = cm.get("units") if isinstance(cm, dict) else None
    base = dict(units) if isinstance(units, dict) else {}
    return units_map_for_system(base, st.session_state.get("unit_system", "imperial"))


def _equip_by_type(frames: dict[str, pd.DataFrame]) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = {}
    for eq_id, df in frames.items():
        et = str(df.attrs.get("equipment_type") or equipment_type_from_id(eq_id))
        buckets.setdefault(et, []).append(eq_id)
    return {k: sorted(v, key=natural_key) for k, v in sorted(buckets.items())}


_PLANT_CHART_META: tuple[tuple[str, str, str], ...] = (
    (PLANT_AIR, "Air side — supply fans", "AHU supply fan status preferred over command."),
    (
        PLANT_BOILER,
        "Boiler plant — HW pumps",
        "One series per HW pump (status preferred over command).",
    ),
    (
        PLANT_CHILLER,
        "Chiller plant — chillers, CHW/CW pumps, towers",
        "Chiller plant uses **mapped pump status** only — no leave-temp fake runtime if no pump."
    ),
)


def _render_plant_motor_weekly(
    motor_weekly: pd.DataFrame,
    *,
    key_prefix: str,
    show_table: bool = True,
    show_download: bool = False,
    min_air_hours: float | None = None,
) -> None:
    """Render three plant-grouped weekly motor charts (avg OAT on secondary axis)."""
    st.markdown("##### Motor run hours by week")
    st.caption(
        "Bars = run hours by week (Mon start). Dotted line = **avg OAT °F while that motor was on**. "
        "Chiller plant uses **pump status** only (no leave-temp if unmapped). "
        "Air side: dashed orange = bare-min occupied hours/week from the building schedule."
    )
    if motor_weekly is None or motor_weekly.empty:
        st.info("No supply-fan / pump / chiller / tower motor signals found yet.")
        return
    any_chart = False
    for plant, title, caption in _PLANT_CHART_META:
        if "plant_group" in motor_weekly.columns:
            sub = motor_weekly.loc[motor_weekly["plant_group"] == plant]
        else:
            sub = motor_weekly.iloc[0:0]
        st.markdown(f"**{title}**")
        st.caption(caption)
        fig = motor_weekly_runtime_chart(
            sub,
            title=title,
            min_hours_line=min_air_hours if plant == "air" else None,
            show_avg_oat=True,
        )
        if fig is None:
            st.info(f"No series for {title.split('—')[0].strip().lower()}.")
            continue
        any_chart = True
        st.plotly_chart(
            fig,
            width="stretch",
            config=plotly_config(filename=f"motor_runtime_weekly_{plant}"),
            key=f"{key_prefix}_motor_weekly_{plant}",
        )
    if not any_chart:
        return
    if show_download:
        st.download_button(
            "Download weekly motor hours CSV",
            to_csv_bytes(motor_weekly),
            "motor_run_hours_weekly.csv",
            key=f"{key_prefix}_dl_motor_weekly",
        )
    if show_table:
        with st.expander("Weekly motor hours table"):
            st.dataframe(motor_weekly, hide_index=True, width="stretch", height=280)


def _mapped_equipment(eq_id: str, frames: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, float]:
    raw = frames[eq_id]
    mapped = apply_role_map(raw, eq_id, st.session_state.role_map)
    # Canonical: Overview weekly calendar always drives occ_mode for SCHED-1.
    sched = OccupancySchedule.from_dict(st.session_state.get("occupancy_schedule"))
    mapped = apply_schedule_occ_mode(mapped, sched, overwrite=True)
    mapped.attrs.update({k: v for k, v in raw.attrs.items() if not isinstance(v, Path)})
    mapped.attrs["equipment_id"] = eq_id
    if raw.attrs.get("columns_path") is not None:
        mapped.attrs["columns_path"] = str(raw.attrs["columns_path"])
    poll = float(raw.attrs.get("poll_seconds") or infer_poll_seconds(raw))
    return mapped, poll


def _run_rule_list(
    eq_ids: list[str],
    rules: list,
    frames: dict[str, pd.DataFrame],
) -> list:
    results = []
    gate_on = bool(st.session_state.get("require_operational_gates", True))
    for eq_id in eq_ids:
        mapped, poll = _mapped_equipment(eq_id, frames)
        for rule in rules:
            results.append(
                run_rule(
                    rule.id,
                    mapped,
                    st.session_state.params.get(rule.id, {}),
                    poll,
                    st.session_state.weather,
                    require_operational_gates=gate_on,
                )
            )
    return results


def _result_lookup(results: list) -> dict[tuple[str, str], object]:
    return {(r.equipment_id, r.rule_id): r for r in results}


def _pick_local_folder() -> str | None:
    """Native OS folder dialog (local Streamlit only). Returns None if cancelled/unavailable."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.wm_attributes("-topmost", 1)
        chosen = filedialog.askdirectory(title="Select building folder (or parent of buildings)")
        root.destroy()
        return chosen or None
    except Exception:
        return None


def _materialize_uploaded_tree(files: list) -> Path | None:
    """Write a browser-picked directory upload into a temp tree and return its root."""
    import tempfile

    if not files:
        return None
    tmp = Path(tempfile.mkdtemp(prefix="vibe19_building_"))
    for f in files:
        rel = getattr(f, "name", None) or "file.csv"
        # Streamlit directory uploads use forward-slash relative paths.
        dest = tmp / Path(*Path(str(rel).replace("\\", "/")).parts)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(f.getvalue())
    candidates = list_building_candidates(tmp)
    if len(candidates) == 1:
        return candidates[0]
    if candidates:
        # Multiple buildings under one upload — prefer deepest common parent already tmp
        return tmp
    return tmp if any(tmp.rglob("history_wide.csv")) else None


def _commit_frames(
    frames: dict[str, pd.DataFrame],
    *,
    site_id: str,
    building_id: str,
    source: str,
    weather,
) -> None:
    if not frames:
        return
    st.session_state.equipment_frames = frames
    st.session_state.weather = weather
    st.session_state.data_source = source
    st.session_state.building_id = building_id
    rm = dict(st.session_state.role_map)
    for eq_id, raw_df in frames.items():
        enrich_role_map_from_equipment(
            rm,
            eq_id,
            Path(raw_df.attrs["columns_path"]) if raw_df.attrs.get("columns_path") else None,
            list(raw_df.columns),
        )
        upsert_equipment_roles(
            st.session_state.site_mapping,
            site_id=str(raw_df.attrs.get("site_id", site_id)),
            building_id=str(raw_df.attrs.get("building_id", building_id)),
            equipment_id=eq_id,
            equipment_type=str(raw_df.attrs.get("equipment_type", equipment_type_from_id(eq_id))),
            roles=rm.get(eq_id, {}),
        )
    st.session_state.role_map = rm
    _sync_role_map_from_sites()
    _attach_frames_meta(frames)
    if st.session_state.selected_equipment not in frames:
        st.session_state.selected_equipment = sorted(frames)[0]


def _commit_package_result(result) -> None:
    """Commit zip package frames + optional session_config into session_state."""
    from app.package_io import apply_session_config

    site_id = st.session_state.site_id or DEFAULT_SITE_ID
    for _eq_id, df in result.frames.items():
        df.attrs.setdefault("site_id", site_id)
        df.attrs.setdefault("building_id", result.manifest.building_id)
        if df.attrs.get("columns_path") is not None:
            df.attrs["columns_path"] = str(df.attrs["columns_path"])
    st.session_state.upload_workdir = str(result.workdir)
    st.session_state.package_report = result.report
    st.session_state.data_input_mode = "Zip package"
    _commit_frames(
        result.frames,
        site_id=site_id,
        building_id=result.manifest.building_id,
        source=f"zip:{result.manifest.building_id}",
        weather=result.weather,
    )
    if result.session_config is not None:
        for w in apply_session_config(result.session_config, equipment_ids=set(result.frames)):
            st.sidebar.warning(w)
        st.session_state.session_config_source = "package session_config.json"
        if result.session_config.params:
            st.session_state.fault_settings_source = "package session_config.params"
    if result.column_map:
        _apply_column_map_json(result.column_map)
        st.session_state.session_config_source = (
            (st.session_state.get("session_config_source") or "") + " + package column_map.json"
        ).strip(" +")
    for w in result.warnings:
        st.sidebar.warning(w)


def _load_from_folder(cfg: AppConfig, folder_text: str) -> None:
    """Load building folder via cached path loaders (local / server paths only).

    Does not wipe an existing zip/folder session when the path is empty or invalid.
    """
    from app.package_io import wipe_workdir

    frames: dict[str, pd.DataFrame] = {}
    weather = None
    building_id = ""
    source = ""
    site_id = st.session_state.site_id or DEFAULT_SITE_ID
    path = Path(folder_text).expanduser() if folder_text else None
    if not folder_text:
        # Keep whatever is already loaded (e.g. user switched source briefly)
        return
    if path and path.is_dir():
        candidates = list_building_candidates(path)
        if not candidates:
            st.sidebar.warning("No `history_wide.csv` under that path.")
            return
        labels = [c.name for c in candidates]
        if len(candidates) == 1 and candidates[0].resolve() == path.resolve():
            chosen = candidates[0]
        else:
            pick = st.sidebar.selectbox("Building", labels, index=0)
            chosen = next(c for c in candidates if c.name == pick)
        building_id = chosen.name
        st.session_state.data_root = str(chosen.parent)
        try:
            frames = cached_building_folder(str(chosen.resolve()))
        except Exception as exc:  # pragma: no cover
            st.sidebar.error(str(exc))
            return
        if not frames:
            st.sidebar.warning("Folder loaded but no equipment frames found.")
            return
        # Successful folder load replaces any prior zip session
        if st.session_state.get("upload_workdir"):
            wipe_workdir(st.session_state.get("upload_workdir"))
            st.session_state.upload_workdir = None
            st.session_state.package_report = None
        for eq_id in frames:
            frames[eq_id].attrs.setdefault("site_id", site_id)
            frames[eq_id].attrs.setdefault("building_id", building_id)
            if frames[eq_id].attrs.get("columns_path") is not None:
                frames[eq_id].attrs["columns_path"] = str(frames[eq_id].attrs["columns_path"])
        weather = cached_weather(str(chosen.parent), cfg.weather_subdir)
        source = str(chosen.resolve())
        from app.package_io import bytes_as_mb, directory_size_bytes, effective_package_caps

        unc = directory_size_bytes(chosen)
        caps = effective_package_caps()
        st.session_state.package_report = {
            "source": "folder",
            "building_id": building_id,
            "equipment_count": len(frames),
            "uncompressed_bytes": unc,
            "uncompressed_mb": bytes_as_mb(unc),
            "max_zip_mb": caps.max_zip_mb,
            "max_uncompressed_mb": caps.max_uncompressed_mb,
        }
        st.sidebar.caption(f"{len(frames)} equip · `{building_id}`")
        _commit_frames(frames, site_id=site_id, building_id=building_id, source=source, weather=weather)
        return
    st.sidebar.caption(
        "Folder path not on this host — use Browse folder…, or switch to Zip package."
    )


def _load_data(cfg: AppConfig) -> None:
    """Unified data picker: Folder (when allowed) + Zip package (always)."""
    from app.package_io import PackageError, load_package_zip, sweep_old_temp_dirs, wipe_workdir

    sweep_old_temp_dirs()
    st.sidebar.markdown("**Building data**")
    mode_label = "Cloud-capable" if cfg.is_cloud else "Local + Cloud-capable"
    st.sidebar.caption(
        f"{mode_label} · same `openfdd_package_v1` zip everywhere "
        f"(`docs/PACKAGE_SPEC.md`). Non-sensitive demo data on shared hosts."
    )

    source_options = ["Zip package"]
    if cfg.allow_server_paths:
        source_options = ["Folder", "Zip package"]
    default_src = "Zip package" if cfg.is_cloud or not cfg.allow_server_paths else "Folder"
    if "data_input_mode" not in st.session_state:
        st.session_state.data_input_mode = default_src
    if st.session_state.data_input_mode not in source_options:
        st.session_state.data_input_mode = source_options[0]
    # Drop a prefilled Folder path that does not exist (Docker / Cloud / missing mount)
    if cfg.allow_server_paths:
        _bf = str(st.session_state.get("building_folder") or "").strip()
        if _bf and not Path(_bf).expanduser().is_dir():
            st.session_state.building_folder = ""
            if st.session_state.data_input_mode == "Folder" and not st.session_state.get("equipment_frames"):
                st.session_state.data_input_mode = "Zip package"
                st.sidebar.caption("Configured folder not found — switched to Zip package.")


    st.sidebar.radio(
        "Data source",
        source_options,
        horizontal=True,
        key="data_input_mode",
        help="Folder = local historian tree. Zip = pre-processed openfdd_package_v1 (Cloud + local).",
    )
    source = st.session_state.data_input_mode

    if source == "Folder" and cfg.allow_server_paths:
        if st.sidebar.button("Browse folder…", help="Pick a building folder on this PC"):
            picked = _pick_local_folder()
            if picked:
                st.session_state.building_folder = picked
                st.rerun()
        folder_text = st.sidebar.text_input(
            "Folder path",
            help="Building folder (AHU_*/… with history_wide.csv), or parent of several buildings.",
            key="building_folder",
        )
        _load_from_folder(cfg, folder_text)
        from app.package_io import dataset_size_caption

        _folder_report = st.session_state.get("package_report")
        if _folder_report:
            st.sidebar.caption(dataset_size_caption(_folder_report))
        if st.session_state.get("equipment_frames") and st.sidebar.button(
            "Clear loaded data", key="clear_folder_session"
        ):
            _clear_uploaded_session()
            st.session_state.building_folder = ""
            st.rerun()
    else:
        from app.package_io import dataset_size_caption, effective_package_caps

        caps = effective_package_caps()
        zip_file = st.sidebar.file_uploader(
            "Building package (.zip)",
            type=["zip"],
            key=f"building_zip_{st.session_state.get('zip_uploader_key', 0)}",
            help="openfdd_package_v1 — manifest.json + equipment history_wide.csv",
        )
        c1, c2 = st.sidebar.columns(2)
        load_clicked = c1.button("Load zip", type="primary", disabled=zip_file is None, key="load_zip_unified")
        clear_clicked = c2.button("Clear session", key="clear_session_unified")
        if clear_clicked:
            _clear_uploaded_session()
            st.rerun()
        if load_clicked and zip_file is not None:
            wipe_workdir(st.session_state.get("upload_workdir"))
            st.session_state.upload_workdir = None
            try:
                result = load_package_zip(zip_file.getvalue())
            except PackageError as exc:
                st.sidebar.error(str(exc))
            except Exception as exc:  # pragma: no cover
                st.sidebar.error(f"Package load failed: {exc}")
            else:
                _commit_package_result(result)
                st.sidebar.success(
                    f"Loaded {len(result.frames)} equip · `{result.manifest.building_id}`"
                )
                st.rerun()

        if cfg.allow_server_paths:
            st.sidebar.markdown("**Agent path load (local)**")
            st.sidebar.text_input(
                "Package zip path",
                help="Absolute path to an openfdd_package_v1 zip (Codex/Cursor — no browser upload).",
                key="package_zip_path",
            )
            if st.sidebar.button("Load zip from path", key="load_zip_from_path"):
                zip_path = Path(str(st.session_state.get("package_zip_path") or "").strip())
                if not zip_path.is_file():
                    st.sidebar.error(f"Zip not found: {zip_path}")
                else:
                    wipe_workdir(st.session_state.get("upload_workdir"))
                    st.session_state.upload_workdir = None
                    try:
                        result = load_package_zip(zip_path.read_bytes())
                    except PackageError as exc:
                        st.sidebar.error(str(exc))
                    except Exception as exc:  # pragma: no cover
                        st.sidebar.error(f"Package load failed: {exc}")
                    else:
                        _commit_package_result(result)
                        st.sidebar.success(
                            f"Loaded {len(result.frames)} equip · `{result.manifest.building_id}`"
                        )
                        st.rerun()

            st.sidebar.text_input(
                "Fault settings JSON path",
                help="Agent-produced fault_settings.json (rule_id → params).",
                key="fault_settings_path",
            )
            if st.sidebar.button("Load fault settings from path", key="load_fault_settings_path"):
                fpath = Path(str(st.session_state.get("fault_settings_path") or "").strip())
                if not fpath.is_file():
                    st.sidebar.error(f"Not found: {fpath}")
                else:
                    try:
                        raw = json.loads(fpath.read_text(encoding="utf-8"))
                        if not isinstance(raw, dict):
                            raise ValueError("JSON must be an object")
                        params = dict(st.session_state.get("params") or {})
                        for rid, p in raw.items():
                            if isinstance(p, dict):
                                params[str(rid)] = {**params.get(str(rid), {}), **p}
                        st.session_state.params = params
                        st.session_state.fault_settings_source = f"path:{fpath.name}"
                        st.sidebar.success(f"Applied fault settings from {fpath.name}")
                        st.rerun()
                    except Exception as exc:
                        st.sidebar.error(f"Fault settings load failed: {exc}")
            st.sidebar.text_input(
                "Session config JSON path",
                help="openfdd_session_v1 JSON (units / role_map / params).",
                key="session_config_path",
            )
            if st.sidebar.button("Load session config from path", key="load_session_config_path"):
                spath = Path(str(st.session_state.get("session_config_path") or "").strip())
                if not spath.is_file():
                    st.sidebar.error(f"Not found: {spath}")
                else:
                    try:
                        warnings = _apply_session_config_bytes(
                            spath.read_bytes(), source_label=f"path:{spath.name}"
                        )
                        for w in warnings:
                            st.sidebar.warning(w)
                        st.sidebar.success(f"Applied session config from {spath.name}")
                        st.rerun()
                    except Exception as exc:
                        st.sidebar.error(f"Session config load failed: {exc}")

        st.sidebar.caption(dataset_size_caption(None, caps=caps))
        report = st.session_state.get("package_report")
        if report:
            st.sidebar.caption(dataset_size_caption(report, caps=caps))
            with st.sidebar.expander("Package report", expanded=False):
                st.json(report)
        frames = st.session_state.get("equipment_frames") or {}
        if frames and st.session_state.get("upload_workdir"):
            st.sidebar.caption(
                f"{len(frames)} equip · `{st.session_state.get('building_id') or '—'}` (zip session)"
            )
        elif frames:
            # Folder data still in session while Zip tab is selected — don't drop it
            st.sidebar.caption(
                f"{len(frames)} equip · `{st.session_state.get('building_id') or '—'}` (session)"
            )

    st.sidebar.markdown("**Session restore (Cloud-safe)**")
    st.sidebar.caption(
        "Download after mapping/tuning; later upload zip + this JSON — no server path."
    )
    with st.sidebar:
        _render_session_config_io(key_prefix="sidebar")

    with st.sidebar.expander("AI agent / package help", expanded=False):
        from app.package_io import effective_package_caps as _caps_fn

        _c = _caps_fn()
        st.markdown(
            f"""
**Agent-friendly flow**
1. Pre-process CSVs into `openfdd_package_v1` (`docs/PACKAGE_SPEC.md`).
2. **Zip package** → upload **or** (local) paste path → **Load zip from path**.
3. Map / tune thresholds → **Download session config** (sidebar or Export).
4. Later (Cloud-safe): upload the **same zip** + **Upload session config** to restore
   `role_map` / `params` / units — no server disk path required.
5. Optional: Mapping tab JSON column map if role_map incomplete.
6. **Clear session** when done (best-effort wipe on shared hosts).

**Effective caps:** zip ≤{_c.max_zip_mb} MB · expanded ≤{_c.max_uncompressed_mb} MB ·
≤{_c.max_entries} entries · ≤{_c.max_equipment} equip  
Default safety limit **500 MB** (zip + expanded). Env: `OPENFDD_MAX_ZIP_MB`, `OPENFDD_MAX_UNCOMPRESSED_MB`, `OPENFDD_MAX_ENTRIES`, `OPENFDD_MAX_EQUIPMENT`.

Agent brief: {_AGENTS_MD_URL}
            """.strip()
        )
        demo = APP_ROOT / "data" / "demo_package_v1.zip"
        if demo.is_file():
            st.caption(f"Demo package on disk: `{demo.name}`")
            st.download_button(
                "Download demo_package_v1.zip",
                data=demo.read_bytes(),
                file_name="demo_package_v1.zip",
                mime="application/zip",
                key="dl_demo_package",
                help="Synthetic non-sensitive package for Cloud / agent dry-runs.",
            )

    st.sidebar.markdown("---")
    st.sidebar.subheader("Display & site")
    st.sidebar.radio(
        "Units",
        ["imperial", "metric"],
        horizontal=True,
        help="Rules stay imperial internally; charts/tables and temp proof sliders convert for display.",
        key="unit_system",
    )
    st.sidebar.checkbox(
        "Prefer web OAT (Open-Meteo)",
        help="Analytics + OAT-dependent views use weather CSV / wx_oa_t before BAS oa_t.",
        key="prefer_web_oat",
    )
    _temp_threshold_slider(
        label_base="CHW leave proof max",
        stored_key="chw_leave_max_f",
        min_f=35.0,
        max_f=50.0,
        step_f=0.5,
        help=(
            "If pump/chiller status is missing, treat CHW supply below this as mechanical cooling on. "
            "Stored as °F; Units radio switches this slider between °F and °C."
        ),
        location=st.sidebar,
    )
    st.session_state.include_ahu_chw_valve = False
    st.session_state.apply_occupancy_calendar = True
    st.sidebar.caption(
        "Occupancy: Overview weekly calendar always sets `occ_mode` (SCHED-1). "
        "Mech-cooling OAT bins: chillers + DX only (no AHU CHW valve)."
    )


def _temp_threshold_slider(
    *,
    label_base: str,
    stored_key: str,
    min_f: float,
    max_f: float,
    step_f: float = 0.5,
    help: str = "",
    location=None,
) -> float:
    """Temp slider that follows Units (°F/°C); always persists imperial °F in ``stored_key``."""
    loc = location if location is not None else st
    system = st.session_state.get("unit_system", "imperial")
    stored = float(st.session_state.get(stored_key, (min_f + max_f) / 2.0))
    stored = max(min_f, min(max_f, stored))
    st.session_state[stored_key] = stored

    unit_marker = f"_{stored_key}_ui_unit"
    widget_key = f"_{stored_key}_ui"

    if system == "metric":
        lo, hi = round(f_to_c(min_f), 1), round(f_to_c(max_f), 1)
        step = max(0.1, round(step_f * 5.0 / 9.0, 1))
        label = f"{label_base} °C"
        if st.session_state.get(unit_marker) != "metric":
            st.session_state[widget_key] = round(f_to_c(stored), 1)
            st.session_state[unit_marker] = "metric"
        cur = float(st.session_state.get(widget_key, f_to_c(stored)))
        st.session_state[widget_key] = max(lo, min(hi, cur))
        new_c = loc.slider(label, min_value=lo, max_value=hi, step=step, help=help, key=widget_key)
        st.session_state[stored_key] = max(min_f, min(max_f, c_to_f(float(new_c))))
    else:
        label = f"{label_base} °F"
        if st.session_state.get(unit_marker) != "imperial":
            st.session_state[widget_key] = stored
            st.session_state[unit_marker] = "imperial"
        cur = float(st.session_state.get(widget_key, stored))
        st.session_state[widget_key] = max(min_f, min(max_f, cur))
        new_f = loc.slider(
            label, min_value=min_f, max_value=max_f, step=step_f, help=help, key=widget_key
        )
        st.session_state[stored_key] = float(new_f)

    return float(st.session_state[stored_key])


def _hhmm_to_time(text: str):
    from datetime import time as dtime

    parts = str(text).strip().split(":")
    h = int(parts[0]) if parts else 6
    m = int(parts[1]) if len(parts) > 1 else 0
    return dtime(max(0, min(23, h)), max(0, min(59, m)))


def _time_to_hhmm(t) -> str:
    return f"{int(t.hour):02d}:{int(t.minute):02d}"


def _sync_zone_comfort_into_params() -> None:
    """Push Overview/sidebar zone band into VAV-1 rule params (FDD starting point)."""
    params = st.session_state.setdefault("params", {})
    vav = dict(params.get("VAV-1") or {})
    vav["zone_lo"] = float(st.session_state.get("zone_lo_f", 68.0))
    vav["zone_hi"] = float(st.session_state.get("zone_hi_f", 76.0))
    params["VAV-1"] = vav
    st.session_state.params = params


def _render_occupancy_editor(*, key_prefix: str) -> OccupancySchedule:
    """Mon–Sun occupied windows with time pickers. Persists to session_state.occupancy_schedule."""
    sched = OccupancySchedule.from_dict(st.session_state.get("occupancy_schedule"))
    tz = st.text_input("Timezone", value=sched.timezone, key=f"{key_prefix}_occ_tz")
    days_out: dict = {}
    for d in DAYS:
        day = sched.days[d]
        st.markdown(f"**{DAY_LABELS[d]}**")
        c1, c2, c3 = st.columns(3)
        occ = c1.checkbox("Occupied", value=day.occupied, key=f"{key_prefix}_occ_{d}")
        start = c2.time_input(
            "Start",
            value=_hhmm_to_time(day.start),
            key=f"{key_prefix}_occ_s_{d}",
        )
        end = c3.time_input(
            "End",
            value=_hhmm_to_time(day.end),
            key=f"{key_prefix}_occ_e_{d}",
        )
        days_out[d] = {
            "occupied": bool(occ),
            "start": _time_to_hhmm(start),
            "end": _time_to_hhmm(end),
        }
    out = {"timezone": tz, "days": days_out}
    st.session_state.occupancy_schedule = out
    return OccupancySchedule.from_dict(out)


def _render_building_schedule_overview() -> float:
    """Main-dashboard occupancy + zone SP; returns bare-min occupied hours/week."""
    st.markdown("##### Building schedule & zone comfort (FDD starting point)")
    st.caption(
        "Occupancy calendar always drives **SCHED-1** (`occ_mode`) — edit times below; do not remove this UI. "
        "Zone low/high seed **VAV-1** comfort band (Units radio switches °F/°C). "
        "Bare-min occupied hours/week draws on air-side motor charts."
    )
    c1, c2, c3 = st.columns(3)
    with c1:
        _temp_threshold_slider(
            label_base="Zone low",
            stored_key="zone_lo_f",
            min_f=55.0,
            max_f=72.0,
            step_f=0.5,
            location=st,
        )
    with c2:
        _temp_threshold_slider(
            label_base="Zone high",
            stored_key="zone_hi_f",
            min_f=70.0,
            max_f=85.0,
            step_f=0.5,
            location=st,
        )
    with c3:
        sched0 = OccupancySchedule.from_dict(st.session_state.get("occupancy_schedule"))
        st.metric("Bare-min occ hours / week", f"{occupied_hours_per_week(sched0):.0f}")
    _sync_zone_comfort_into_params()
    with st.expander("Edit weekly occupancy (time pickers)", expanded=True):
        sched = _render_occupancy_editor(key_prefix="overview")
    return occupied_hours_per_week(
        OccupancySchedule.from_dict(st.session_state.get("occupancy_schedule"))
    )


def _site_mapping_tab(cfg: AppConfig, selected: str, raw_df: pd.DataFrame) -> None:
    st.subheader("Site / building / equipment mapping")
    sites = st.session_state.site_mapping
    site_ids = sorted(sites.keys()) or [DEFAULT_SITE_ID]
    sid = st.selectbox("Site", site_ids, key="map_site")
    site = sites.setdefault(sid, Site(site_id=sid, site_name=sid))
    bids = sorted(site.buildings.keys()) or [DEFAULT_BUILDING_ID]
    bid = st.selectbox("Building", bids, key="map_bldg")
    building = site.buildings.setdefault(bid, Building(building_id=bid, building_name=bid, site_id=sid))
    etype = st.selectbox("Equipment type", ["AHU", "VAV", "CHW_PLANT", "BOILER", "HP", "WEATHER", "METER", "UNKNOWN"], index=0, key="map_etype")
    st.write(f"Editing equipment **{selected}**")
    inferred = {**suggest_roles(raw_df), **roles_from_columns_csv(Path(raw_df.attrs.get("columns_path")) if raw_df.attrs.get("columns_path") else None)}
    edit = dict(st.session_state.role_map.get(selected, {}))
    for role in sorted(set(list(inferred.keys()) + list(edit.keys()) + ["zone_t", "sat", "sat_sp", "oa_t", "fan_cmd"])):
        opts = [""] + list(raw_df.columns)
        cur = edit.get(role, inferred.get(role, ""))
        edit[role] = st.selectbox(role, opts, index=opts.index(cur) if cur in opts else 0, key=f"sm_{selected}_{role}")
    edit = {k: v for k, v in edit.items() if v}
    st.session_state.role_map[selected] = edit
    upsert_equipment_roles(sites, site_id=sid, building_id=bid, equipment_id=selected, equipment_type=etype, roles=edit)
    _sync_role_map_from_sites()
    c1, c2, c3 = st.columns(3)
    if c1.button("Save flat YAML"):
        if not cfg.allow_disk_writes:
            st.warning("Shared/Cloud host: use Export download — server disk writes are disabled.")
        else:
            save_role_map(cfg.role_map_path, st.session_state.role_map, nested=False)
            st.success("Saved flat role_map.yaml")
    if c2.button("Save nested site YAML"):
        if not cfg.allow_disk_writes:
            st.warning("Shared/Cloud host: use Export download — server disk writes are disabled.")
        else:
            save_site_mapping(cfg.role_map_path, sites)
            st.success("Saved nested sites YAML")
    if c3.button("Export nested YAML download"):
        st.download_button("Download nested mapping", yaml.safe_dump({"sites": {s: st.session_state.site_mapping[s].to_dict() for s in st.session_state.site_mapping}}, sort_keys=False), "site_mapping.yaml")


def main() -> None:
    _init_state()
    cfg = AppConfig.load()
    defaults_cfg = cached_rule_defaults(str(cfg.rule_defaults_path))
    _apply_agent_bootstrap_once()
    _load_data(cfg)
    _sidebar_sliders(defaults_cfg)

    if st.session_state.get("bootstrap_status"):
        st.sidebar.caption(f"Agent bootstrap: {st.session_state.bootstrap_status}")

    frames = st.session_state.equipment_frames
    if not frames:
        _empty_state_directions()
        return

    # Sidebar "Rerun cat." — apply after frames exist
    pending = st.session_state.pop("_pending_rerun_family", "__none__")
    if pending != "__none__":
        rules = RULES if pending is None else _rules_by_family().get(pending, [])
        st.session_state.batch_results = _run_rule_list(sorted(frames), rules, frames)
        label = "all rules" if pending is None else family_label(pending)
        st.toast(f"Reran {label}: {len(st.session_state.batch_results)} evaluations")

    eq_ids = sorted(frames, key=natural_key)
    selected = st.selectbox("Equipment", eq_ids, index=eq_ids.index(st.session_state.selected_equipment) if st.session_state.selected_equipment in eq_ids else 0)
    st.session_state.selected_equipment = selected
    mapped, poll = _mapped_equipment(selected, frames)
    kind = infer_equipment_kind(selected)
    units_map = _units_map()
    by_type = _equip_by_type(frames)

    tabs = st.tabs(
        [
            "Overview",
            "Data & Mapping",
            "Run Rules",
            "Results by Category",
            "Plots",
            "RCx Plots",
            "Analytics",
            "Export",
        ]
    )

    span = dataset_time_span(frames)
    motor_tbl = motor_run_hours_table(frames, st.session_state.role_map)
    motor_tot = motor_run_hours_totals(motor_tbl)
    try:
        motor_weekly = motor_run_hours_weekly(
            frames,
            st.session_state.role_map,
            chw_leave_max_f=float(st.session_state.get("chw_leave_max_f", 48.0)),
            weather=st.session_state.weather,
            prefer_web_oat=bool(st.session_state.get("prefer_web_oat", True)),
        )
    except Exception as exc:
        st.warning(f"Weekly motor hours unavailable: {exc}")
        motor_weekly = pd.DataFrame()
    try:
        cool_bins = mech_cooling_oat_bins(
            frames,
            st.session_state.role_map,
            weather=st.session_state.weather,
            prefer_web_oat=bool(st.session_state.get("prefer_web_oat", True)),
            chw_leave_max_f=float(st.session_state.get("chw_leave_max_f", 48.0)),
            include_ahu_chw_valve=False,
        )
    except Exception as exc:
        st.warning(f"Mech-cooling OAT bins unavailable: {exc}")
        cool_bins = pd.DataFrame()
    start_s = span["start"].strftime("%Y-%m-%d %H:%M") if span["start"] is not None else "—"
    end_s = span["end"].strftime("%Y-%m-%d %H:%M") if span["end"] is not None else "—"

    with tabs[0]:
        st.subheader("Overview")
        st.markdown(
            """
**Workflow reminder**

| Piece | What | Where |
| --- | --- | --- |
| **1. Data package** | Folder or zip of CSVs (`openfdd_package_v1`) | Sidebar → Folder / Zip |
| **2. Data model** | Column→role JSON *or* zip / uploaded `session_config` role_map | **Data & Mapping** / sidebar |
| **3. Tune + save** | Download `session_config.json` (params + role_map) | Sidebar **Session restore** or **Export** |
| **4. Run** | 50-rule cookbook → charts | **Run Rules** → **Plots** / **RCx Plots** |
| **5. Restore later** | Upload zip + session config (Cloud-safe round-trip) | Sidebar uploaders |

Round-trip: **upload zip → map/tune → download session_config → later upload zip + session_config**.
            """.strip()
        )
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Equipment", len(frames))
        _n_custom = len(RULES) - CANONICAL_RULE_COUNT
        c2.metric(
            "Rules",
            (
                f"{CANONICAL_RULE_COUNT} (+{_n_custom} custom)"
                if _n_custom > 0
                else str(CANONICAL_RULE_COUNT)
            ),
        )
        c3.metric("Rows (selected)", len(mapped))
        c4.metric("Poll (s)", f"{poll:.0f}")
        c5.metric("Kind", kind)
        st.caption(f"`{st.session_state.data_source}`")
        _pkg_rep = st.session_state.get("package_report") or {}
        _size_bits = []
        if _pkg_rep.get("zip_mb") is not None:
            _size_bits.append(f"{_pkg_rep['zip_mb']} MB zip")
        if _pkg_rep.get("uncompressed_mb") is not None:
            _size_bits.append(f"{_pkg_rep['uncompressed_mb']} MB on disk")
        if _size_bits:
            _lim_z = _pkg_rep.get("max_zip_mb", "—")
            _lim_u = _pkg_rep.get("max_uncompressed_mb", "—")
            st.caption(
                f"Dataset size: {' · '.join(str(b) for b in _size_bits)} "
                f"(limits {_lim_z} / {_lim_u} MB)"
            )

        d1, d2, d3 = st.columns(3)
        d1.metric("Dataset start", start_s)
        d2.metric("Dataset end", end_s)
        d3.metric("Span (h)", f"{span['span_hours']:.1f}")

        min_air_hours = _render_building_schedule_overview()
        _render_plant_motor_weekly(
            motor_weekly,
            key_prefix="overview",
            show_table=True,
            min_air_hours=min_air_hours,
        )

        st.markdown("##### Mechanical cooling hours by OAT bin")
        st.caption(
            "**Chillers** (mapped pump / status / amps / power — **no leave-temp**) + "
            "**AHU/HP DX compressors** only. Never CHW cooling valves. "
            "Bins sorted cold→hot; OAT from **web** weather by default."
        )
        cool_fig = mech_cooling_oat_histogram(cool_bins)
        if cool_fig is None:
            st.info(
                "No compressor / chiller-plant proof found. Map chw_pump_status (or DX compressor). "
                "Unmapped chillers are omitted (no leave-temp fake hours). AHU CHW valves excluded."
            )
        else:
            st.plotly_chart(
                cool_fig,
                width="stretch",
                config=plotly_config(filename="mech_cooling_oat_bins"),
                key="overview_cool_bins",
            )
            st.dataframe(cool_bins, hide_index=True, width="stretch", height=280)
            st.download_button(
                "Download mech cooling OAT bins CSV",
                to_csv_bytes(cool_bins),
                "mech_cooling_oat_bins.csv",
                key="dl_cool_bins_overview",
            )

        st.markdown(
            "Tune thresholds in the **left sidebar** → **Run Rules** (all or by category) "
            "or sidebar **Rerun cat.** → browse **Plots** by device type (AHU / VAV / plant…)."
        )
        st.markdown("**Devices by type**")
        type_counts = pd.DataFrame(
            [{"type": t, "count": len(ids)} for t, ids in by_type.items()]
        )
        st.dataframe(type_counts, hide_index=True, width="stretch")

    with tabs[1]:
        st.subheader("Data & column → role mapping")
        st.write(
            "Map historian columns with Haystack-like `points` (or Auto-build). "
            "Units in the JSON keep plots from mixing families."
        )
        raw_df = frames[selected]
        map_cols = st.columns(2)
        with map_cols[0]:
            st.markdown("##### JSON column map (LLM / heuristic)")
            bid = st.session_state.building_id or "building"
            default_json = APP_ROOT / "configs" / f"{bid.lower()}_column_map.json"
            if not default_json.is_file():
                demo = APP_ROOT / "configs" / "building_100_column_map.json"
                # Demo map is a template any site can start from — not locked to BUILDING_100.
                default_json = demo if demo.is_file() else default_json
            if cfg.allow_server_paths:
                json_path = st.text_input(
                    "JSON map path (optional)",
                    st.session_state.column_map_path or (str(default_json) if default_json.is_file() else ""),
                )
                if st.button("Load JSON map from path") and json_path:
                    try:
                        data = load_column_map_json(json_path)
                        _apply_column_map_json(data)
                        st.session_state.column_map_path = json_path
                        st.success(f"Loaded map for {len(data.get('equipment', {}))} equipment")
                    except Exception as exc:
                        st.error(str(exc))
            uploaded_json = st.file_uploader("Or upload column map JSON", type=["json"], key="colmap_upload")
            if uploaded_json is not None and st.button("Apply uploaded JSON map"):
                try:
                    import json as _json

                    data = normalize_column_map(_json.loads(uploaded_json.getvalue().decode("utf-8")))
                    _apply_column_map_json(data)
                    st.success(f"Applied uploaded map ({len(data.get('equipment', {}))} equipment)")
                except Exception as exc:
                    st.error(str(exc))
            if st.button("Auto-build JSON map from loaded CSVs"):
                data = build_column_map_from_equipment_frames(
                    frames,
                    building_id=st.session_state.building_id,
                    site_ref=st.session_state.site_id,
                    generated_by="heuristic",
                )
                _apply_column_map_json(data)
                issues = validate_column_map_against_frames(data, frames)
                if not cfg.allow_disk_writes:
                    st.success(
                        f"Built Haystack map in session ({len(data['equipment'])} equip) — "
                        "shared/Cloud host: download JSON (no server disk write)."
                    )
                    st.download_button(
                        "Download column map JSON",
                        data=__import__("json").dumps(data, indent=2),
                        file_name=f"{(st.session_state.building_id or 'building').lower()}_column_map.json",
                        mime="application/json",
                        key="dl_colmap_cloud",
                    )
                else:
                    out_name = f"{(st.session_state.building_id or 'building').lower()}_column_map.json"
                    out = APP_ROOT / "configs" / out_name
                    save_column_map_json(out, data, haystack=True)
                    st.session_state.column_map_path = str(out)
                    st.success(f"Built & saved Haystack map `{out.name}` ({len(data['equipment'])} equip)")
                if issues:
                    st.warning("\n".join(issues[:15]))

        with map_cols[1]:
            st.markdown("##### LLM workflow (Haystack points → cookbook roles)")
            filled_prompt = build_llm_prompt_for_frames(
                frames,
                building_id=st.session_state.building_id,
                site_ref=st.session_state.site_id,
            )
            with st.expander("Filled LLM prompt", expanded=False):
                st.code(filled_prompt, language="text")
            st.download_button(
                "Download LLM prompt as .txt",
                data=filled_prompt.encode("utf-8"),
                file_name=f"{(st.session_state.building_id or 'building').lower()}_llm_column_map_prompt.txt",
                mime="text/plain",
                key="dl_llm_prompt",
            )
            if st.session_state.column_map:
                st.download_button(
                    "Download Haystack column map JSON",
                    data=__import__("json").dumps(
                        to_haystack_document(st.session_state.column_map), indent=2
                    ).encode(),
                    file_name="column_map.json",
                    mime="application/json",
                    key="dl_colmap_mapping_tab",
                )

            from app.role_map_gap import build_role_map_gap_report

            with st.expander("Role map gap report", expanded=False):
                gap_df = build_role_map_gap_report(
                    frames,
                    st.session_state.role_map,
                    weather=st.session_state.weather,
                )
                st.dataframe(gap_df, hide_index=True, width="stretch", height=280)
                st.download_button(
                    "Download role_map_gap_report.csv",
                    to_csv_bytes(gap_df),
                    "role_map_gap_report.csv",
                    key="dl_gap_mapping",
                )

        st.divider()
        st.markdown("##### Per-equipment role editor")
        st.caption(
            "Optional manual override per CSV / device. Skip this if the LLM (or Auto-build) JSON map "
            "already assigned the right columns — only use these dropdowns to fix gaps or mistakes."
        )
        inferred = {
            **suggest_roles(raw_df),
            **roles_from_columns_csv(Path(raw_df.attrs.get("columns_path")) if raw_df.attrs.get("columns_path") else None),
        }
        edit = dict(st.session_state.role_map.get(selected, {}))
        for role in sorted(set(list(inferred.keys()) + list(edit.keys()) + ["zone_t", "sat", "sat_sp", "oa_t", "fan_cmd"])):
            opts = [""] + list(raw_df.columns)
            cur = edit.get(role, inferred.get(role, ""))
            edit[role] = st.selectbox(
                role,
                opts,
                index=opts.index(cur) if cur in opts else 0,
                key=f"r_{selected}_{role}",
            )
        edit = {k: v for k, v in edit.items() if v}
        st.session_state.role_map[selected] = edit
        if st.button("Save role map YAML"):
            if not cfg.allow_disk_writes:
                st.download_button(
                    "Download role_map.yaml",
                    yaml.safe_dump(st.session_state.role_map, sort_keys=True),
                    "role_map.yaml",
                    key="dl_role_map_cloud",
                )
                st.info("Shared/Cloud host: download only (no server write).")
            else:
                save_role_map(cfg.role_map_path, st.session_state.role_map)
                st.success("Saved role_map.yaml")
        with st.expander("Site / building nesting"):
            _site_mapping_tab(cfg, selected, raw_df)
        st.divider()
        st.markdown("##### Raw data preview")
        issues = validate_dataframe(raw_df)
        st.write("Validation:", issues or "OK")
        st.dataframe(raw_df.head(100), width="stretch")

    with tabs[2]:
        st.subheader("Run rules")
        st.caption(
            "Sidebar sliders only store thresholds — they do **not** re-evaluate rules. "
            "Click **Run** here (or sidebar **Rerun cat.**) after tuning."
        )
        scope = st.radio(
            "Equipment scope",
            ["selected equipment", "all equipment"],
            horizontal=True,
            key="run_scope",
        )
        mode = st.radio(
            "Rule set",
            ["All 50 rules", "One mechanical category"],
            horizontal=True,
            key="run_mode",
        )
        fam_key = None
        if mode == "One mechanical category":
            labels = [family_label(f) for f in FAMILY_ORDER if _rules_by_family().get(f)]
            pick = st.selectbox("Category", labels, key="run_fam_label")
            fam_key = {family_label(f): f for f in FAMILY_ORDER}[pick]

        if st.button("Run", type="primary", key="run_btn"):
            target_rules = RULES if fam_key is None else _rules_by_family().get(fam_key, [])
            eq_list = [selected] if scope == "selected equipment" else sorted(frames, key=natural_key)
            st.session_state.batch_results = _run_rule_list(eq_list, target_rules, frames)
            st.success(f"Ran {len(st.session_state.batch_results)} evaluations — open **Plots** or **Analytics**.")

    with tabs[3]:
        st.subheader("Results by mechanical category")
        results = st.session_state.batch_results
        if not results:
            st.info("Run rules (main tab or sidebar **Rerun cat.**), then review here or on **Plots**.")
        else:
            summary = results_summary_table(results)
            m1, m2, m3, m4, m5, m6 = st.columns(6)
            m1.metric("PASS", int((summary["status"] == "PASS").sum()))
            m2.metric("FAULT", int((summary["status"] == "FAULT").sum()))
            m3.metric("SKIPPED", int((summary["status"] == "SKIPPED_MISSING_ROLES").sum()))
            m4.metric("EQUIP OFF", int((summary["status"] == "SKIPPED_EQUIPMENT_OFF").sum()))
            m5.metric("N/A", int((summary["status"] == "NOT_APPLICABLE_EQUIPMENT_TYPE").sum()))
            m6.metric("ERROR", int((summary["status"] == "ERROR").sum()))
            by_fam = _results_by_family(summary)
            fam_tabs = st.tabs([family_label(f) for f in by_fam])
            for tab, (fam, part) in zip(fam_tabs, by_fam.items()):
                with tab:
                    st.dataframe(part, width="stretch", height=420)
                    faults = part[part["status"] == "FAULT"]
                    if not faults.empty:
                        st.write("**Faults**")
                        st.dataframe(faults.sort_values("fault_hours", ascending=False), width="stretch")

    with tabs[4]:
        st.subheader("Plots by device")
        st.caption(
            "Pick a mechanical type → device (each AHU / VAV / plant unit has its own plots). "
            "Each rule is one figure: rainbow-colored signals on unique unit axes, "
            "confirmed fault as a shaded swim lane. Camera icon → PNG/JPEG."
        )
        plot_fmt = st.selectbox("Download format", ["png", "jpeg", "svg", "webp"], index=0, key="plot_fmt")
        show_pass = st.checkbox("Show PASS plots (not only FAULT)", value=False, key="plot_show_pass")
        type_opts = list(by_type.keys()) or ["UNKNOWN"]
        cur_type = str(frames[selected].attrs.get("equipment_type") or equipment_type_from_id(selected))
        type_idx = type_opts.index(cur_type) if cur_type in type_opts else 0
        eq_type = st.selectbox("Device type", type_opts, index=type_idx, key="plot_eq_type")
        device_ids = by_type.get(eq_type, [])
        if not device_ids:
            st.warning("No devices of that type.")
        else:
            dev_idx = device_ids.index(selected) if selected in device_ids else 0
            device = st.selectbox("Device", device_ids, index=dev_idx, key="plot_device")
            st.session_state.selected_equipment = device
            plot_df, _ = _mapped_equipment(device, frames)
            eq_kind = infer_equipment_kind(device)

            applicable = [r for r in RULES if eq_kind in r.equipment_kinds or eq_kind == "unknown"]
            by_fam_rules: dict[str, list] = {f: [] for f in FAMILY_ORDER}
            for rule in applicable:
                fam = rule.family if rule.family in by_fam_rules else "other"
                by_fam_rules[fam].append(rule)

            lookup = _result_lookup(st.session_state.batch_results)
            if st.button("Run all applicable rules for this device", type="primary", key="plot_run_device"):
                new_res = _run_rule_list([device], applicable, frames)
                keep = [r for r in st.session_state.batch_results if r.equipment_id != device]
                st.session_state.batch_results = keep + new_res
                lookup = _result_lookup(st.session_state.batch_results)
                st.success(f"Evaluated {len(new_res)} rules on `{device}`")

            if not any(eq == device for eq, _rid in lookup):
                st.info("Click **Run all applicable rules for this device** (or sidebar **Rerun cat.**) to populate plots.")

            # Sensor fault summary statistics (SV-* FAULT results)
            device_results = [r for r in st.session_state.batch_results if r.equipment_id == device]
            sens = sensor_fault_summary(plot_df, device_results, equipment_id=device)
            if not sens.empty:
                st.markdown("##### Sensor fault summary statistics")
                st.caption("Mean/std/min/p50/max for sensors involved in FAULT sensor-validation rules — useful for engineer review and CSV export.")
                st.dataframe(sens, width="stretch", height=220)
                st.download_button(
                    "Download sensor fault stats CSV",
                    to_csv_bytes(sens),
                    f"{device}_sensor_fault_stats.csv",
                    key=f"dl_sens_{device}",
                )

            shown = 0
            for fam in FAMILY_ORDER:
                rules = by_fam_rules.get(fam) or []
                if not rules:
                    continue
                with st.expander(
                    f"{family_label(fam)} · {len(rules)} rules for {eq_type}",
                    expanded=(fam in {"ahu", "vav", "control"} and eq_type in {"AHU", "VAV"}),
                ):
                    for rule in rules:
                        r = lookup.get((device, rule.id))
                        if r is None:
                            st.caption(f"{rule.id} — {rule.title} · not run yet")
                            continue
                        if r.status in {"SKIPPED_MISSING_ROLES", "NOT_APPLICABLE_EQUIPMENT_TYPE", "ERROR", "SKIPPED_EQUIPMENT_OFF"}:
                            with st.container(border=True):
                                st.markdown(f"**{rule.id}** — {rule.title}")
                                st.caption(f"`{r.status}` · {rule.equation}")
                                if r.missing_roles:
                                    st.caption("Missing: " + ", ".join(r.missing_roles))
                            continue
                        if r.status == "PASS" and not show_pass:
                            continue
                        with st.container(border=True):
                            st.markdown(f"**{rule.id}** — {rule.title}")
                            fh = r.fault_hours if r.fault_hours is not None else 0.0
                            st.caption(f"`{r.status}` · fault hours: {fh:.2f}")
                            st.caption(rule.equation)
                            fig = rule_result_chart(
                                plot_df,
                                r,
                                required_roles=rule.required_roles,
                                units_map=units_map,
                            )
                            if fig:
                                st.plotly_chart(
                                    fig,
                                    width="stretch",
                                    config=plotly_config(filename=f"{device}_{rule.id}", fmt=plot_fmt),
                                    key=f"fig_{device}_{rule.id}",
                                )
                                shown += 1
                            else:
                                st.caption("No plot series for this result.")
            if shown == 0 and any(eq == device for eq, _rid in lookup):
                st.info(
                    "No FAULT plots to show — enable **Show PASS plots**, or check column mapping / run results."
                )

    with tabs[5]:
        try:
            render_rcx_plots_tab(
                frames,
                st.session_state.role_map,
                weather=st.session_state.weather,
                unit_system=st.session_state.get("unit_system", "imperial"),
            )
        except Exception as exc:
            st.error(f"RCx Plots failed: {exc}")

    with tabs[6]:
        st.subheader("Analytics")
        st.caption(
            "Weekly motor runtime and mechanical cooling vs **web** OAT "
            "(same views as Overview — detail tables + CSV downloads here)."
        )
        b1, b2, b3 = st.columns(3)
        b1.metric("Dataset start", start_s)
        b2.metric("Dataset end", end_s)
        b3.metric("Span (h)", f"{span['span_hours']:.1f}")

        _render_plant_motor_weekly(
            motor_weekly,
            key_prefix="analytics",
            show_table=False,
            show_download=True,
            min_air_hours=occupied_hours_per_week(
                OccupancySchedule.from_dict(st.session_state.get("occupancy_schedule"))
            ),
        )
        if not motor_tbl.empty:
            with st.expander("Lifetime totals by motor signal"):
                st.dataframe(motor_tbl, width="stretch", height=280)
                st.caption(
                    f"Preferred-signal rollup — fans {motor_tot['fan_hours']:.1f} h · "
                    f"pumps {motor_tot['pump_hours']:.1f} h · total {motor_tot['total_hours']:.1f} h"
                )

        st.markdown("##### Mechanical cooling hours by OAT bin")
        cool_fig2 = mech_cooling_oat_histogram(cool_bins)
        if cool_fig2 is None:
            st.info(
                "No mechanical-cooling proof available. Map chiller pump/status (or amps/power) "
                "or AHU/HP DX compressor roles (`compressor_status`, `dx_stage`, …) and load weather/. "
                "CHW cooling valves are never used for this chart."
            )
        else:
            st.plotly_chart(
                cool_fig2,
                width="stretch",
                config=plotly_config(filename="mech_cooling_oat_bins_analytics"),
                key="analytics_cool_hist",
            )
            st.dataframe(cool_bins, hide_index=True, width="stretch", height=280)
            st.download_button(
                "Download mech cooling OAT bins CSV",
                to_csv_bytes(cool_bins),
                "mech_cooling_oat_bins.csv",
                key="dl_cool_bins",
            )

    with tabs[7]:
        st.subheader("Export")
        st.caption(
            "Plotly camera → PNG/JPEG. Cloud-safe: download/upload session_config + fault_settings "
            "(same controls as sidebar). Agent loop: zip ↔ session_config ↔ summary CSV."
        )
        results = st.session_state.batch_results
        if results:
            summary = results_summary_table(results)
            st.download_button("Summary CSV", to_csv_bytes(summary), "fdd_summary.csv")
        st.markdown("##### Session restore")
        _render_session_config_io(key_prefix="export")
        if st.session_state.column_map:
            st.download_button(
                "Haystack column map JSON",
                data=__import__("json").dumps(
                    to_haystack_document(st.session_state.column_map), indent=2
                ).encode(),
                file_name="column_map.json",
                mime="application/json",
                key="dl_colmap_export",
            )
        if frames:
            from app.role_map_gap import build_role_map_gap_report

            gap_df = build_role_map_gap_report(
                frames,
                st.session_state.role_map,
                weather=st.session_state.weather,
            )
            if not gap_df.empty:
                st.markdown("##### Role map gap report")
                st.dataframe(gap_df, hide_index=True, width="stretch", height=280)
                st.download_button(
                    "Download role_map_gap_report.csv",
                    to_csv_bytes(gap_df),
                    "role_map_gap_report.csv",
                    key="dl_gap_export",
                )
            try:
                from app.tuning_report import build_tuning_assistant_report

                trep = build_tuning_assistant_report(
                    tuned=results or [],
                    params=st.session_state.get("params") or {},
                    has_web_weather=st.session_state.weather is not None,
                    gap_report=gap_df,
                )
                st.download_button(
                    "Download tuning_assistant_report.json",
                    data=__import__("json").dumps(trep, indent=2, default=str).encode("utf-8"),
                    file_name="tuning_assistant_report.json",
                    mime="application/json",
                    key="dl_tuning_report",
                )
            except Exception:
                pass


if __name__ == "__main__":
    main()
