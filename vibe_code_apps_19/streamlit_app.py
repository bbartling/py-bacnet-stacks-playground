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
    bas_vs_web_oat_histogram,
    energy_degree_day_scatter,
    max_plot_points,
    mech_cooling_oat_histogram,
    monthly_energy_bar,
    motor_weekly_runtime_chart,
    plotly_config,
    rule_result_chart,
)
from app.config import AppConfig  # noqa: E402
from app.dashboard_contract import REQUIRED_MAIN_SECTIONS  # noqa: E402
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
from app.site_model import (  # noqa: E402
    EQUIPMENT_TYPES,
    Building,
    Site,
    resolve_equipment_type,
    stamp_equipment_type,
)

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
3. **Run** — **Run Rules** → **FDD Plots** / **RCx Plots**
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
        "**Start here:** sidebar → **Building package zip(s)** (or Folder locally). "
        "Each equipment CSV needs a sibling Haystack map JSON. Then **Run Rules** → **FDD Plots** / **RCx**."
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
        "prerun_status": "",
        "package_warnings": [],
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
        "vav_to_ahu": {},
        "require_operational_gates": True,
        "unit_system": "imperial",
        "prefer_web_oat": True,
        "chw_leave_max_f": 48.0,
        "include_ahu_chw_valve": False,  # hard-coded; never offer in UI
        "occupancy_schedule": OccupancySchedule().to_dict(),
        "apply_occupancy_calendar": True,  # always on; Overview calendar → occ_mode
        "zone_lo_f": 70.0,
        "zone_hi_f": 75.0,
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
    for eq_id, block in (normalized.get("equipment") or {}).items():
        roles = dict(block.get("column_roles") or {})
        etype = resolve_equipment_type(
            eq_id,
            role_map=st.session_state.role_map,
            column_map=normalized,
            explicit=str(block.get("equipment_type") or ""),
        )
        # Persist type in role_map meta for session_config round-trip
        meta = dict(st.session_state.role_map.get(eq_id) or {})
        meta.update(roles)
        meta["equipment_type"] = etype
        st.session_state.role_map[eq_id] = meta
        upsert_equipment_roles(
            st.session_state.site_mapping,
            site_id=st.session_state.site_id,
            building_id=st.session_state.building_id,
            equipment_id=eq_id,
            equipment_type=etype,
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


_STATUS_SORT = {
    "FAULT": 0,
    "WARNING": 1,
    "PASS": 2,
    "SKIPPED_MISSING_ROLES": 3,
    "SKIPPED_EQUIPMENT_OFF": 4,
    "ERROR": 5,
    "NOT_APPLICABLE_EQUIPMENT_TYPE": 6,
    "NOT_RUN": 7,
}


def _device_results_table(summary: pd.DataFrame, equipment_id: str) -> pd.DataFrame:
    """Compact per-device results: FAULT/PASS first, N/A last; include rule title."""
    part = summary[summary["equipment_id"] == equipment_id].copy()
    if part.empty:
        return part
    titles = {r.id: r.title for r in RULES}
    fams = {r.id: r.family for r in RULES}
    part["title"] = part["rule_id"].map(lambda rid: titles.get(str(rid), ""))
    part["rule_family"] = part["rule_id"].map(lambda rid: fams.get(str(rid), "other"))
    # natural_key returns a list — cannot use sort_values on list cells (unhashable).
    part = part.loc[
        sorted(
            part.index,
            key=lambda i: (
                _STATUS_SORT.get(str(part.at[i, "status"]), 99),
                natural_key(str(part.at[i, "rule_id"])),
            ),
        )
    ]
    cols = [
        "rule_id",
        "title",
        "rule_family",
        "status",
        "fault_hours",
        "fault_pct",
        "missing_roles",
        "notes",
    ]
    return part[[c for c in cols if c in part.columns]].reset_index(drop=True)


def _status_counts(df: pd.DataFrame) -> dict[str, int]:
    if df.empty or "status" not in df.columns:
        return {}
    return {str(k): int(v) for k, v in df["status"].value_counts().items()}


def _attach_frames_meta(frames: dict[str, pd.DataFrame]) -> None:
    rm = st.session_state.role_map
    cm = st.session_state.get("column_map")
    sites = st.session_state.site_mapping
    for eq_id, df in frames.items():
        sid, bid, etype = equipment_context(sites, eq_id)
        df.attrs.setdefault("site_id", sid)
        df.attrs.setdefault("building_id", bid)
        stamp_equipment_type(
            df,
            eq_id,
            role_map=rm,
            column_map=cm if isinstance(cm, dict) else None,
            sites=sites,
            explicit=etype,
        )
        # Optional plant_group meta from role_map
        pg = (rm.get(eq_id) or {}).get("plant_group")
        if pg:
            df.attrs["plant_group"] = str(pg)
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
    rm = st.session_state.get("role_map") or {}
    for eq_id, df in frames.items():
        et = resolve_equipment_type(eq_id, df=df, role_map=rm)
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
        "Chiller plant prefers **mapped pump status**; if no pump, falls back to "
        "chiller_status / compressor_status / equipment_enable — never leave-temp fake runtime."
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
        "Chiller plant prefers **pump status**, then chiller/compressor enable "
        "(no leave-temp fake hours). "
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
    # Topology enrich: parent AHU SAT may live only on the raw VAV frame
    if "ahu_sat" in raw.columns and "ahu_sat" not in mapped.columns:
        mapped["ahu_sat"] = raw["ahu_sat"]
    elif "ahu_sat" in raw.columns:
        mapped["ahu_sat"] = raw["ahu_sat"]
    # Canonical: Overview weekly calendar always drives occ_mode for SCHED-1.
    sched = OccupancySchedule.from_dict(st.session_state.get("occupancy_schedule"))
    mapped = apply_schedule_occ_mode(mapped, sched, overwrite=True)
    mapped.attrs.update({k: v for k, v in raw.attrs.items() if not isinstance(v, Path)})
    mapped.attrs["equipment_id"] = eq_id
    if raw.attrs.get("columns_path") is not None:
        mapped.attrs["columns_path"] = str(raw.attrs["columns_path"])
    poll = float(raw.attrs.get("poll_seconds") or infer_poll_seconds(raw))
    return mapped, poll


def _ensure_ahu_feed_enrichment(frames: dict[str, pd.DataFrame]) -> None:
    """Refresh ahu_sat / feed attrs from session topology before running rules."""
    from app.topology_enrich import enrich_frames_with_ahu_feeds, stamp_feed_attrs

    topo = st.session_state.get("vav_to_ahu") or {}
    if not topo:
        return
    stamp_feed_attrs(frames, topo)
    enrich_frames_with_ahu_feeds(frames, topo, role_map=st.session_state.get("role_map") or {})


def _run_rule_list(
    eq_ids: list[str],
    rules: list,
    frames: dict[str, pd.DataFrame],
) -> list:
    _ensure_ahu_feed_enrichment(frames)
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


def _preferred_plot_rule_id(applicable: list, lookup: dict, device: str) -> str | None:
    """First FAULT/WARNING rule, else first with a result, else first applicable."""
    if not applicable:
        return None
    ranked: list[tuple[int, str]] = []
    for rule in applicable:
        res = lookup.get((device, rule.id))
        status = str(getattr(res, "status", "") or "")
        if status in {"FAULT", "WARNING"}:
            ranked.append((0, rule.id))
        elif status in {"PASS", "SKIPPED_MISSING_ROLES", "SKIPPED_EQUIPMENT_OFF", "ERROR"}:
            ranked.append((1, rule.id))
        elif res is not None:
            ranked.append((2, rule.id))
        else:
            ranked.append((3, rule.id))
    ranked.sort(key=lambda t: t[0])
    return ranked[0][1]


def _ensure_device_rules_run(device: str, applicable: list, frames: dict[str, pd.DataFrame]) -> bool:
    """Run applicable rules for device if missing. Returns True when a rerun is needed."""
    lookup = _result_lookup(st.session_state.batch_results)
    if any(eq == device for eq, _rid in lookup):
        return False
    if not applicable:
        return False
    new_res = _run_rule_list([device], applicable, frames)
    keep = [r for r in st.session_state.batch_results if r.equipment_id != device]
    st.session_state.batch_results = keep + new_res
    focus_key = f"plot_chart_rule_{device}"
    pref = _preferred_plot_rule_id(applicable, _result_lookup(st.session_state.batch_results), device)
    if pref:
        label = next((f"{r.id} — {r.title}" for r in applicable if r.id == pref), None)
        if label:
            st.session_state[focus_key] = label
    return True


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
            equipment_type=resolve_equipment_type(eq_id, df=raw_df, role_map=rm),
            roles=rm.get(eq_id, {}),
        )
    st.session_state.role_map = rm
    _sync_role_map_from_sites()
    _attach_frames_meta(frames)
    if st.session_state.selected_equipment not in frames:
        st.session_state.selected_equipment = sorted(frames)[0]


def _render_package_health_sidebar(report: dict | None, warnings: list[str] | None = None) -> None:
    """Dataset details expander — health notes at the bottom (never a red error banner)."""
    report = report or {}
    warnings = list(warnings or [])
    health = report.get("package_health") if isinstance(report.get("package_health"), dict) else None
    summary = list(report.get("package_health_summary") or [])
    grade = str(report.get("package_health_grade") or (health or {}).get("grade") or "").lower()
    detail = list((health or {}).get("detail_lines") or [])
    other = [w for w in warnings if w not in detail and w not in summary]

    has_size = report.get("zip_mb") is not None or report.get("uncompressed_mb") is not None
    if not (health or summary or detail or other or has_size or report.get("building_id")):
        return

    label = "Dataset details"
    if grade and grade not in {"", "ok"}:
        label = f"Dataset details · {grade}"

    with st.sidebar.expander(label, expanded=False):
        bits: list[str] = []
        if report.get("building_id"):
            bits.append(f"`{report.get('building_id')}`")
        if report.get("equipment_count") is not None:
            bits.append(f"{report.get('equipment_count')} equip")
        if report.get("source"):
            bits.append(str(report.get("source")))
        if bits:
            st.caption(" · ".join(bits))
        if has_size:
            from app.package_io import dataset_size_caption

            st.caption(dataset_size_caption(report))

        if detail:
            st.caption("Contract findings (load still succeeded):")
            for line in detail[:40]:
                st.text(line)
            if len(detail) > 40:
                st.caption(f"… +{len(detail) - 40} more (see Export / package_health.json)")

        for w in other[:15]:
            st.caption(w)
        if len(other) > 15:
            st.caption(f"… +{len(other) - 15} more")

        # Health summary last — informational, not an error banner
        if summary or grade:
            st.divider()
            st.caption("Dataset health (non-fatal)")
            for line in summary:
                # Strip markdown bold so caption stays muted
                st.caption(str(line).replace("**", ""))
            if not summary and grade:
                st.caption(
                    f"Dataset health: {grade.upper()} "
                    "(non-fatal — load succeeded; topology/metadata may be incomplete)."
                )

        with st.expander("Raw package report JSON", expanded=False):
            st.json(report)


def _commit_package_result(result) -> None:
    """Commit zip package frames + optional session_config into session_state."""
    from app.data_contract import load_vav_to_ahu_map
    from app.package_io import apply_session_config
    from app.topology_enrich import enrich_frames_with_ahu_feeds, stamp_feed_attrs

    site_id = st.session_state.site_id or DEFAULT_SITE_ID
    for _eq_id, df in result.frames.items():
        df.attrs.setdefault("site_id", site_id)
        df.attrs.setdefault("building_id", result.manifest.building_id)
        if df.attrs.get("columns_path") is not None:
            df.attrs["columns_path"] = str(df.attrs["columns_path"])

    topo = load_vav_to_ahu_map(result.building_root)
    st.session_state.vav_to_ahu = topo
    result.report["vav_to_ahu"] = dict(topo)
    result.report["vav_to_ahu_count"] = len(topo)
    stamp_feed_attrs(result.frames, topo)
    enrich_frames_with_ahu_feeds(
        result.frames, topo, role_map=st.session_state.get("role_map") or {}
    )

    st.session_state.upload_workdir = str(result.workdir)
    st.session_state.package_report = result.report
    # Do not assign ``data_input_mode`` here — it is a radio widget key. Setting it
    # after the radio is drawn (Load zip / path load) raises StreamlitAPIException.
    # Prefer Zip package on the *next* run via a pending flag applied before the radio.
    st.session_state["_pending_data_input_mode"] = "Zip package"
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
        # Re-enrich after role_map merge so ahu_sat uses updated mappings
        enrich_frames_with_ahu_feeds(
            st.session_state.equipment_frames,
            st.session_state.get("vav_to_ahu") or topo,
            role_map=st.session_state.get("role_map") or {},
        )
    # Sidebar Dataset details is rendered from _load_data on each run (not here —
    # avoids a red banner flash and duplicate expanders before st.rerun).
    st.session_state.package_warnings = list(
        (result.report or {}).get("package_health_summary") or result.warnings
    )


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


def _docker_image_caption() -> str | None:
    """Human-readable GHCR/local image identity (avoids bare content hashes in the UI)."""
    import os

    ref = (os.environ.get("VIBE19_IMAGE_REF") or "").strip()
    tag = (os.environ.get("VIBE19_IMAGE_TAG") or "").strip()
    sha = (os.environ.get("VIBE19_GIT_SHA") or "").strip()
    if not ref and not tag and not sha:
        return None
    name = f"{ref}:{tag}" if ref and tag else (ref or tag or "vibe19")
    short = sha[:12] if sha and sha != "unknown" else ""
    return f"Image: `{name}`" + (f" · sha `{short}`" if short else "")


def _load_data(cfg: AppConfig) -> None:
    """Unified data picker: Folder (when allowed) + Zip package (always)."""
    from app.package_io import PackageError, load_package_zip, sweep_old_temp_dirs, wipe_workdir

    sweep_old_temp_dirs()
    st.sidebar.markdown("**Building data**")
    img_cap = _docker_image_caption()
    if img_cap:
        st.sidebar.caption(img_cap)
    mode_label = "Cloud-capable" if cfg.is_cloud else "Local + Cloud-capable"
    st.sidebar.caption(
        f"{mode_label} · same `openfdd_package_v1` zip everywhere "
        f"(`docs/PACKAGE_SPEC.md`). Non-sensitive demo data on shared hosts."
    )

    source_options = ["Zip package"]
    if cfg.allow_server_paths:
        source_options = ["Folder", "Zip package"]
    default_src = "Zip package" if cfg.is_cloud or not cfg.allow_server_paths else "Folder"
    pending = st.session_state.pop("_pending_data_input_mode", None)
    if pending in source_options:
        st.session_state.data_input_mode = pending
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
            _render_package_health_sidebar(
                _folder_report,
                st.session_state.get("package_warnings") or [],
            )
        if st.session_state.get("equipment_frames") and st.sidebar.button(
            "Clear loaded data", key="clear_folder_session"
        ):
            _clear_uploaded_session()
            st.session_state.building_folder = ""
            st.rerun()
    else:
        from app.package_io import (
            BROWSER_UPLOAD_MB,
            dataset_size_caption,
            effective_package_caps,
        )

        browser_caps = effective_package_caps(for_browser_upload=True)
        agent_caps = effective_package_caps()
        zip_files = st.sidebar.file_uploader(
            "Building package zip(s)",
            type=["zip"],
            accept_multiple_files=True,
            key=f"building_zip_{st.session_state.get('zip_uploader_key', 0)}",
            help=(
                f"Upload one building openfdd zip, or several part-zips "
                f"(each ≤{BROWSER_UPLOAD_MB} MB; assembled ≤{agent_caps.max_zip_mb} MB). "
                f"Optional extra weather.zip is merged/ignored safely. "
                f"Limits also count zip items (each file/folder inside the archive), "
                f"not just megabytes — max {agent_caps.max_entries} items / "
                f"{agent_caps.max_equipment} equipment folders. "
                f"See vibe19_agent_spec/docs/AGENT_CSV_PREPROCESS.md"
            ),
        )
        n_parts = len(zip_files or [])
        parts_mb = (
            round(sum(getattr(f, "size", 0) or len(f.getvalue()) for f in zip_files) / (1024 * 1024), 2)
            if zip_files
            else 0.0
        )
        st.sidebar.caption(
            f"**{n_parts}** file(s) · **{parts_mb} MB** selected · "
            f"per-file ≤**{BROWSER_UPLOAD_MB} MB** · assembled job ≤**{agent_caps.max_zip_mb} MB**"
        )
        st.sidebar.caption(
            f"Build check: zip-item limit **{agent_caps.max_entries}** "
            f"(each file/folder inside the archive) · equip ≤**{agent_caps.max_equipment}**. "
            f"If you still see **200**, `docker pull` the latest "
            f"`ghcr.io/bbartling/vibe19:develop` — that machine is on an old image."
        )
        c1, c2 = st.sidebar.columns(2)
        load_clicked = c1.button(
            "Load zip(s)",
            type="primary",
            disabled=not zip_files,
            key="load_zip_unified",
        )
        clear_clicked = c2.button("Clear session", key="clear_session_unified")
        if clear_clicked:
            _clear_uploaded_session()
            st.rerun()
        if load_clicked and zip_files:
            wipe_workdir(st.session_state.get("upload_workdir"))
            st.session_state.upload_workdir = None
            try:
                if len(zip_files) == 1:
                    result = load_package_zip(zip_files[0].getvalue(), caps=browser_caps)
                else:
                    from app.multi_zip import load_package_from_zip_parts, parts_from_uploads

                    result = load_package_from_zip_parts(
                        parts_from_uploads(list(zip_files)),
                        merge_caps=agent_caps,
                        per_part_caps=browser_caps,
                    )
            except PackageError as exc:
                st.sidebar.error(str(exc))
            except Exception as exc:  # pragma: no cover
                st.sidebar.error(f"Package load failed: {exc}")
            else:
                _commit_package_result(result)
                part_note = (
                    f" · {result.report.get('zip_part_count', 1)} zip part(s)"
                    if result.report.get("source") == "multi_zip"
                    else ""
                )
                st.sidebar.success(
                    f"Loaded {len(result.frames)} equip · `{result.manifest.building_id}`{part_note}"
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

        st.sidebar.caption(dataset_size_caption(None, caps=agent_caps))
        report = st.session_state.get("package_report")
        if report:
            st.sidebar.caption(dataset_size_caption(report, caps=agent_caps))
            _render_package_health_sidebar(
                report,
                st.session_state.get("package_warnings") or [],
            )
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

    frames_ready = bool(st.session_state.get("equipment_frames"))
    if frames_ready:
        st.sidebar.markdown("**Agent prerun**")
        st.sidebar.caption(
            "After zip(s) load: auto-build column map if needed, then run all rules "
            "so Plots/RCx are ready for human review."
        )
        if st.sidebar.button("Map + prerun all faults", type="primary", key="agent_prerun_btn"):
            from app.agent_prerun import ensure_column_map

            frames = st.session_state.equipment_frames
            cmap, built, warns = ensure_column_map(
                frames,
                existing_map=st.session_state.get("column_map_json"),
                building_id=str(st.session_state.get("building_id") or ""),
            )
            for w in warns:
                st.sidebar.info(w)
            if built and cmap:
                _apply_column_map_json(cmap)
                st.session_state.column_map_json = cmap
            st.session_state.batch_results = _run_rule_list(
                sorted(frames), RULES, frames
            )
            n = len(st.session_state.batch_results)
            err = sum(1 for r in st.session_state.batch_results if r.status == "ERROR")
            fault = sum(1 for r in st.session_state.batch_results if r.status == "FAULT")
            st.session_state.prerun_status = (
                f"Prerun {n} evals · {fault} FAULT · {err} ERROR"
            )
            if err:
                st.sidebar.error(st.session_state.prerun_status)
            else:
                st.sidebar.success(st.session_state.prerun_status)
            st.rerun()
        if st.session_state.get("prerun_status"):
            st.sidebar.caption(st.session_state.prerun_status)

    with st.sidebar.expander("AI agent / package help", expanded=False):
        from app.package_io import BROWSER_UPLOAD_MB, DEFAULT_PACKAGE_MB
        from app.package_io import effective_package_caps as _caps_fn

        _c = _caps_fn()
        st.markdown(
            f"""
**Human + agent flow (large jobs)**
1. Agent preprocesses CSVs → one or many `openfdd_package_v1` **part zips**
   (each ≤ **{BROWSER_UPLOAD_MB} MB** for the browser). Spec:
   `vibe19_agent_spec/docs/AGENT_CSV_PREPROCESS.md`
2. Human uploads **all part zips** here → **Load zip(s)** (merged ≤ **{DEFAULT_PACKAGE_MB} MB**).
3. Click **Map + prerun all faults** (or agent CLI) so rules/errors are checked.
4. Human reviews **Plots / RCx**; download session config to restore later.

**Single zip** still works. Path/CLI bypasses the upload widget for full-size packages.

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
        help="OAT-dependent views use weather CSV / wx_oa_t before BAS oa_t.",
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
    """Push Overview/sidebar zone band into VAV-1 and SCHED-1 rule params."""
    params = st.session_state.setdefault("params", {})
    lo = float(st.session_state.get("zone_lo_f", 70.0))
    hi = float(st.session_state.get("zone_hi_f", 75.0))
    vav = dict(params.get("VAV-1") or {})
    vav["zone_lo"] = lo
    vav["zone_hi"] = hi
    params["VAV-1"] = vav
    sched = dict(params.get("SCHED-1") or {})
    sched["comfort_low_f"] = lo
    sched["comfort_high_f"] = hi
    params["SCHED-1"] = sched
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
    type_opts = list(EQUIPMENT_TYPES)
    cur_type = resolve_equipment_type(
        selected,
        df=raw_df,
        role_map=st.session_state.role_map,
        column_map=st.session_state.get("column_map"),
        sites=sites,
    )
    type_idx = type_opts.index(cur_type) if cur_type in type_opts else 0
    etype = st.selectbox(
        "Equipment type",
        type_opts,
        index=type_idx,
        key=f"map_etype_{selected}",
        help="RTU → choose AHU (DX roles). Heat pump → HP. Persists into session_config role_map meta.",
    )
    st.write(f"Editing equipment **{selected}**")
    inferred = {**suggest_roles(raw_df), **roles_from_columns_csv(Path(raw_df.attrs.get("columns_path")) if raw_df.attrs.get("columns_path") else None)}
    edit = dict(st.session_state.role_map.get(selected, {}))
    for role in sorted(set(list(inferred.keys()) + list(edit.keys()) + ["zone_t", "sat", "sat_sp", "oa_t", "fan_cmd", "chw_pump_status", "chw_pump_equipment"])):
        if role in {"equipment_type", "equipType", "plant_group", "notes"}:
            continue
        opts = [""] + list(raw_df.columns)
        cur = edit.get(role, inferred.get(role, ""))
        if role == "chw_pump_equipment":
            eq_opts = [""] + sorted(st.session_state.equipment_frames)
            cur_link = str(edit.get("chw_pump_equipment") or "")
            edit["chw_pump_equipment"] = st.selectbox(
                "chw_pump_equipment (linked)",
                eq_opts,
                index=eq_opts.index(cur_link) if cur_link in eq_opts else 0,
                key=f"sm_{selected}_chw_pump_equipment",
                help="Optional: equipment id that owns the CHW pump status column.",
            )
            continue
        edit[role] = st.selectbox(role, opts, index=opts.index(cur) if cur in opts else 0, key=f"sm_{selected}_{role}")
    edit = {k: v for k, v in edit.items() if v}
    edit["equipment_type"] = etype
    st.session_state.role_map[selected] = edit
    raw_df.attrs["equipment_type"] = etype
    upsert_equipment_roles(
        sites,
        site_id=sid,
        building_id=bid,
        equipment_id=selected,
        equipment_type=etype,
        roles=edit,
    )
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
    kind = infer_equipment_kind(
        selected, df=frames.get(selected), role_map=st.session_state.role_map
    )
    units_map = _units_map()
    by_type = _equip_by_type(frames)

    _MAIN_SECTIONS = list(REQUIRED_MAIN_SECTIONS)
    section = st.radio(
        "Section",
        _MAIN_SECTIONS,
        horizontal=True,
        key="main_section",
        label_visibility="collapsed",
    )
    st.caption(
        f"Plot traces capped at **{max_plot_points():,}** points "
        "(env `VIBE19_MAX_PLOT_POINTS`) — full data still used for rules/exports."
    )

    span = dataset_time_span(frames)
    motor_tbl = motor_run_hours_table(frames, st.session_state.role_map)
    motor_tot = motor_run_hours_totals(motor_tbl)
    motor_weekly = pd.DataFrame()
    cool_bins = pd.DataFrame()
    if section == "Overview":
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
    start_s = span["start"].strftime("%Y-%m-%d %H:%M") if span["start"] is not None else "—"
    end_s = span["end"].strftime("%Y-%m-%d %H:%M") if span["end"] is not None else "—"

    if section == "Overview":
        st.subheader("Overview")
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

        st.markdown("##### BAS vs web outdoor-air temperature")
        st.caption(
            "Histogram of **BAS OAT − web OAT** (°F) when both series exist. "
            "Uses mapped `bas_oa_t`/`oa_t` vs `wx_oa_t` (package weather). "
            "Empty when web weather or BAS OAT is missing."
        )
        wx_fig = bas_vs_web_oat_histogram(
            frames,
            st.session_state.role_map,
            weather=st.session_state.weather,
        )
        if wx_fig is None:
            st.info("Need both BAS outdoor-air temp and web weather OAT to plot the deviation histogram.")
        else:
            st.plotly_chart(
                wx_fig,
                width="stretch",
                config=plotly_config(filename="bas_vs_web_oat_hist"),
                key="overview_bas_web_oat",
            )

        st.markdown(
            "Tune thresholds in the **left sidebar** → **Run Rules** (all or by category) "
            "or sidebar **Rerun cat.** → browse **FDD Plots** by device type (AHU / VAV / plant…)."
        )
        st.markdown("**Devices by type**")
        type_counts = pd.DataFrame(
            [{"type": t, "count": len(ids)} for t, ids in by_type.items()]
        )
        st.dataframe(type_counts, hide_index=True, width="stretch")

    if section == "Data Model":
        from app.data_model_tree import build_data_model_tree
        from app.docx_report import build_building_data_model_docx

        st.subheader("Data model tree")
        st.caption(
            "Professional inventory: equipment → cookbook roles → Haystack-like tags → raw CSV columns. "
            "AHU↔VAV **feeds / fedBy** come from package `vav_to_ahu_simple.csv` when present "
            "(never invented). Missing mappings show as empty placeholders."
        )
        tree = build_data_model_tree(
            frames,
            st.session_state.role_map,
            building_id=st.session_state.get("building_id") or "",
            vav_to_ahu=st.session_state.get("vav_to_ahu")
            or (st.session_state.get("package_report") or {}).get("vav_to_ahu"),
        )
        topo_n = len(tree.vav_to_ahu or {})
        if topo_n:
            st.caption(f"Topology: **{topo_n}** VAV→AHU link(s) loaded from package.")
        for eq in tree.equipment:
            feed_bits = []
            if eq.fed_by:
                feed_bits.append(f"fedBy `{eq.fed_by}`")
            if eq.feeds:
                feed_bits.append(f"feeds {len(eq.feeds)} VAV(s)")
            title = f"{eq.equipment_id} · {eq.equipment_type}"
            if feed_bits:
                title += " · " + " · ".join(feed_bits)
            with st.expander(title, expanded=False):
                if eq.fed_by:
                    st.markdown(f"**fedBy (parent AHU):** `{eq.fed_by}`")
                if eq.feeds:
                    st.markdown("**feeds (VAV children):** " + ", ".join(f"`{v}`" for v in eq.feeds))
                if not eq.bindings:
                    st.info("No role bindings yet — include a sibling Haystack JSON next to this equipment CSV in the zip.")
                else:
                    rows = [
                        {
                            "Cookbook role": b.cookbook_role,
                            "Haystack-like tag": b.haystack_tag,
                            "CSV column": b.csv_column or "—",
                            "In history": "yes" if b.present_in_history else "no",
                            "Rules": ", ".join(b.required_by_rules[:8])
                            + ("…" if len(b.required_by_rules) > 8 else ""),
                        }
                        for b in eq.bindings
                    ]
                    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", height=280)
                st.caption(f"{len(eq.applicable_rule_ids)} applicable cookbook rules for this type")
        try:
            docx_bytes = build_building_data_model_docx(tree)
            st.download_button(
                "Download data_model.docx",
                data=docx_bytes,
                file_name=f"{(st.session_state.get('building_id') or 'building')}_data_model.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key="dl_data_model_docx",
            )
        except Exception as exc:
            st.warning(f"DOCX unavailable: {exc}")
        flat = pd.DataFrame(tree.to_rows())
        if not flat.empty:
            st.download_button(
                "Download data_model.csv",
                to_csv_bytes(flat),
                "data_model.csv",
                key="dl_data_model_csv",
            )

        st.divider()
        st.markdown("##### Mapping status")
        st.caption(
            "Maps load from the package: each equipment `history_wide.csv` needs a sibling "
            "`history_wide.json` / `history_wide.column_map.json` / `column_map.json`. "
            "Weather CSV maps are optional. Upload zips via the sidebar."
        )
        from app.role_map_gap import build_role_map_gap_report

        gap_df = build_role_map_gap_report(
            frames,
            st.session_state.role_map,
            weather=st.session_state.weather,
        )
        if not gap_df.empty:
            st.dataframe(gap_df, hide_index=True, width="stretch", height=280)
            st.download_button(
                "Download role_map_gap_report.csv",
                to_csv_bytes(gap_df),
                "role_map_gap_report.csv",
                key="dl_gap_data_model",
            )
        if st.session_state.get("column_map"):
            st.download_button(
                "Download merged column map JSON",
                data=__import__("json").dumps(
                    to_haystack_document(st.session_state.column_map), indent=2
                ).encode(),
                file_name="column_map.json",
                mime="application/json",
                key="dl_colmap_data_model",
            )
        with st.expander("Advanced: edit roles for selected device", expanded=False):
            raw_df = frames[selected]
            inferred = {
                **suggest_roles(raw_df),
                **roles_from_columns_csv(
                    Path(raw_df.attrs.get("columns_path"))
                    if raw_df.attrs.get("columns_path")
                    else None
                ),
            }
            edit = dict(st.session_state.role_map.get(selected, {}))
            for role in sorted(
                set(
                    list(inferred.keys())
                    + list(edit.keys())
                    + ["zone_t", "sat", "sat_sp", "oa_t", "fan_cmd"]
                )
            ):
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
            st.caption(
                "Overrides apply in-session; prefer fixing the package sidecar JSON for lasting maps."
            )


    if section == "Run Rules":
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
            [f"All {CANONICAL_RULE_COUNT} rules", "One mechanical category"],
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
            st.success(
                f"Ran {len(st.session_state.batch_results)} evaluations — "
                "open **FDD Plots** for the FDD Word template, or **RCx Plots**."
            )

    if section == "Results by Category":
        st.subheader("Results by equipment type")
        st.caption(
            "Organized by **device type** (AHU / VAV / plant…), then one table per device. "
            "Not by cookbook rule family — so boilers never appear under AHU."
        )
        results = st.session_state.batch_results
        if not results:
            st.info("Run rules (main tab or sidebar **Rerun cat.**), then review here or on **FDD Plots**.")
        else:
            summary = results_summary_table(results)
            m1, m2, m3, m4, m5, m6 = st.columns(6)
            m1.metric("PASS", int((summary["status"] == "PASS").sum()))
            m2.metric("FAULT", int((summary["status"] == "FAULT").sum()))
            m3.metric("SKIPPED", int((summary["status"] == "SKIPPED_MISSING_ROLES").sum()))
            m4.metric("EQUIP OFF", int((summary["status"] == "SKIPPED_EQUIPMENT_OFF").sum()))
            m5.metric("N/A", int((summary["status"] == "NOT_APPLICABLE_EQUIPMENT_TYPE").sum()))
            m6.metric("ERROR", int((summary["status"] == "ERROR").sum()))

            hide_na = st.checkbox(
                "Hide N/A rows (NOT_APPLICABLE_EQUIPMENT_TYPE)",
                value=True,
                key="results_hide_na",
                help="N/A means the rule does not apply to this equipment type — hide to scan FAULT/PASS faster.",
            )
            view = summary
            if hide_na and not view.empty:
                view = view[view["status"] != "NOT_APPLICABLE_EQUIPMENT_TYPE"]

            # Prefer live typed buckets; fall back to types stamped on results
            type_order = list(by_type.keys()) if by_type else []
            if not type_order and "equipment_type" in summary.columns:
                type_order = sorted(
                    {str(t) for t in summary["equipment_type"].dropna().unique()},
                    key=natural_key,
                )

            for eq_type in type_order:
                device_ids = list(by_type.get(eq_type) or [])
                if not device_ids:
                    # Results-only devices of this type
                    device_ids = sorted(
                        summary.loc[summary["equipment_type"] == eq_type, "equipment_id"]
                        .astype(str)
                        .unique(),
                        key=natural_key,
                    )
                type_rows = view[view["equipment_id"].isin(device_ids)] if not view.empty else view
                if type_rows.empty and hide_na:
                    # Still show type if it has devices but only N/A left
                    raw_type = summary[summary["equipment_id"].isin(device_ids)]
                    if raw_type.empty:
                        continue
                counts = _status_counts(
                    summary[summary["equipment_id"].isin(device_ids)]
                    if not summary.empty
                    else summary
                )
                bits = " · ".join(f"{k} {v}" for k, v in sorted(counts.items(), key=lambda kv: _STATUS_SORT.get(kv[0], 99)))
                st.markdown(f"### {eq_type} · {len(device_ids)} device(s)")
                if bits:
                    st.caption(bits)

                for eq_id in sorted(device_ids, key=natural_key):
                    tbl = _device_results_table(view if hide_na else summary, eq_id)
                    if tbl.empty:
                        # Device present but filtered out / not run
                        raw_tbl = _device_results_table(summary, eq_id)
                        if raw_tbl.empty:
                            st.markdown(f"**`{eq_id}`** — no results yet")
                            continue
                        n_na = int((raw_tbl["status"] == "NOT_APPLICABLE_EQUIPMENT_TYPE").sum())
                        st.markdown(f"**`{eq_id}`**")
                        st.caption(f"Only N/A rows ({n_na}) — uncheck **Hide N/A** to show.")
                        continue
                    n_fault = int((tbl["status"] == "FAULT").sum())
                    n_pass = int((tbl["status"] == "PASS").sum())
                    st.markdown(
                        f"**`{eq_id}`** — {len(tbl)} row(s)"
                        + (f" · FAULT {n_fault}" if n_fault else "")
                        + (f" · PASS {n_pass}" if n_pass else "")
                    )
                    st.dataframe(tbl, hide_index=True, width="stretch", height=min(420, 48 + 28 * len(tbl)))

            st.download_button(
                "Download full results CSV",
                to_csv_bytes(summary),
                "fdd_results_by_equipment.csv",
                key="dl_results_by_equip",
            )

    if section == "FDD Plots":
        from app.docx_report import applicable_rules_for_equipment, build_equipment_fdd_docx
        from app.rule_card import (
            build_rule_card,
            equipment_mapping_coverage,
            filter_status_bucket,
        )

        st.subheader("FDD Plots — rule validation")
        st.caption(
            "Pick a device → rules auto-run → **chart on top**. "
            "Cards below = params + mapping. Camera icon on chart → PNG/JPEG. "
            "One Plotly at a time (low-RAM)."
        )
        st.caption(
            "Economizer **ECON-1…4**, **OA-1**, **DMP-1**, **FC8–11** need OA damper / MAT / OAT "
            "(`oa_damper_pct` → e.g. `mad_c`). **ECON-5** needs heat/preheat. "
            "**FC6** needs AHU `vav_total_flow`. Empty plots are usually **data gaps**."
        )

        type_opts = list(by_type.keys()) or ["UNKNOWN"]
        cur_type = resolve_equipment_type(
            selected, df=frames[selected], role_map=st.session_state.role_map
        )
        type_idx = type_opts.index(cur_type) if cur_type in type_opts else 0
        c_type, c_dev, c_fmt = st.columns([1, 1.2, 0.8])
        with c_type:
            eq_type = st.selectbox("Device type", type_opts, index=type_idx, key="plot_eq_type")
        device_ids = by_type.get(eq_type, [])
        if not device_ids:
            st.warning("No devices of that type.")
        else:
            with c_dev:
                dev_idx = device_ids.index(selected) if selected in device_ids else 0
                device = st.selectbox("Device", device_ids, index=dev_idx, key="plot_device")
            with c_fmt:
                plot_fmt = st.selectbox(
                    "Chart download", ["png", "jpeg", "svg", "webp"], index=0, key="plot_fmt"
                )
            st.session_state.selected_equipment = device
            plot_df, _ = _mapped_equipment(device, frames)
            applicable = applicable_rules_for_equipment(
                device,
                equipment_type=eq_type,
                mapped_df=plot_df,
                role_map=st.session_state.role_map,
            )
            present_n, total_n, cov_pct = equipment_mapping_coverage(
                applicable, device, st.session_state.role_map, plot_df
            )

            # Auto-run when this device has no evaluations yet
            if _ensure_device_rules_run(device, applicable, frames):
                st.rerun()

            lookup = _result_lookup(st.session_state.batch_results)

            # Device data strip
            n_rows = int(len(plot_df)) if plot_df is not None and not plot_df.empty else 0
            t0 = t1 = "—"
            if plot_df is not None and not plot_df.empty and isinstance(plot_df.index, pd.DatetimeIndex):
                t0 = str(plot_df.index.min())[:19]
                t1 = str(plot_df.index.max())[:19]
            device_map = dict((st.session_state.role_map or {}).get(device) or {})
            mapped_roles = [
                k for k, v in device_map.items()
                if k not in {"equipment_type", "plant_group"} and v
            ]
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("History rows", f"{n_rows:,}")
            s2.metric("Mapped roles", len(mapped_roles))
            s3.metric("Mapping coverage", f"{cov_pct:.0f}%", help=f"{present_n}/{total_n} unique required roles")
            s4.metric("Rule cards", len(applicable))
            if n_rows:
                st.caption(f"History span: `{t0}` → `{t1}`")

            # Downloads + rerun
            d1, d2, d3, d4 = st.columns([1.1, 1.1, 1.2, 1])
            with d1:
                try:
                    session_bytes = json.dumps(_session_config_payload(), indent=2).encode("utf-8")
                except Exception:
                    session_bytes = json.dumps(
                        {
                            "schema_version": "openfdd_session_v1",
                            "role_map": st.session_state.get("role_map") or {},
                            "params": st.session_state.get("params") or {},
                        },
                        indent=2,
                    ).encode("utf-8")
                st.download_button(
                    "Download session_config.json",
                    data=session_bytes,
                    file_name="session_config.json",
                    mime="application/json",
                    key=f"dl_session_plots_{device}",
                    help="Current units, prefer_web_oat, full role_map, params.",
                )
            with d2:
                role_bytes = json.dumps(
                    st.session_state.get("role_map") or {}, indent=2
                ).encode("utf-8")
                st.download_button(
                    "Download role_map.json",
                    data=role_bytes,
                    file_name="role_map.json",
                    mime="application/json",
                    key=f"dl_rolemap_plots_{device}",
                    help="Equipment → role → CSV column mapping only.",
                )
            with d3:
                try:
                    docx_bytes = build_equipment_fdd_docx(
                        building_id=st.session_state.get("building_id") or "",
                        equipment_id=device,
                        equipment_type=eq_type,
                        results=st.session_state.batch_results,
                        role_map=st.session_state.role_map,
                        mapped_df=plot_df,
                        plot_png_by_rule={},
                        params=st.session_state.get("params") or {},
                        rules=applicable,
                    )
                    st.download_button(
                        "Download FDD DOCX",
                        data=docx_bytes,
                        file_name=f"{device}_fdd_report.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key=f"dl_fdd_docx_{device}",
                        type="primary",
                        help="Simple Word template: description + equation + empty plot slot per rule.",
                    )
                except Exception as exc:
                    st.warning(f"DOCX unavailable: {exc}")
            with d4:
                if st.button("Re-run device rules", key="plot_run_device"):
                    new_res = _run_rule_list([device], applicable, frames)
                    keep = [r for r in st.session_state.batch_results if r.equipment_id != device]
                    st.session_state.batch_results = keep + new_res
                    lookup = _result_lookup(st.session_state.batch_results)
                    pref = _preferred_plot_rule_id(applicable, lookup, device)
                    if pref:
                        st.session_state[f"plot_chart_rule_{device}"] = next(
                            (f"{r.id} — {r.title}" for r in applicable if r.id == pref),
                            st.session_state.get(f"plot_chart_rule_{device}"),
                        )
                    st.rerun()

            device_results = [r for r in st.session_state.batch_results if r.equipment_id == device]
            n_fault = sum(1 for r in device_results if r.status == "FAULT")
            n_pass = sum(1 for r in device_results if r.status == "PASS")
            n_skip = sum(
                1
                for r in device_results
                if str(r.status).startswith("SKIPPED")
            )
            st.caption(
                f"`{device}` · {len(applicable)} applicable rules · "
                f"FAULT {n_fault} · PASS {n_pass} · SKIPPED {n_skip} · "
                f"{len(device_results)} evaluations"
            )

            # Chart panel (always on top — never default to "none")
            focus_labels = [f"{r.id} — {r.title}" for r in applicable]
            focus_key = f"plot_chart_rule_{device}"
            if focus_labels:
                pref_id = _preferred_plot_rule_id(applicable, lookup, device)
                pref_label = next(
                    (lab for lab in focus_labels if lab.startswith(f"{pref_id} —")),
                    focus_labels[0],
                )
                if focus_key not in st.session_state or st.session_state[focus_key] not in focus_labels:
                    st.session_state[focus_key] = pref_label
                focus_pick = st.selectbox(
                    "Chart rule (one Plotly at a time)",
                    focus_labels,
                    key=focus_key,
                )
                focus_rule_id = focus_pick.split(" — ", 1)[0].strip()
                focus_rule = next((r for r in applicable if r.id == focus_rule_id), None)
                focus_res = lookup.get((device, focus_rule_id))
                st.markdown(f"##### Chart · `{focus_rule_id}`")
                if focus_rule is None:
                    st.info("No applicable rules for this device type.")
                elif focus_res is None:
                    st.warning("No result for this rule — click **Re-run device rules**.")
                else:
                    status = str(getattr(focus_res, "status", "") or "")
                    st.caption(f"Status: `{status}`")
                    fig = rule_result_chart(
                        plot_df,
                        focus_res,
                        required_roles=focus_rule.required_roles,
                        units_map=units_map,
                    )
                    if fig:
                        st.plotly_chart(
                            fig,
                            width="stretch",
                            config=plotly_config(
                                filename=f"{device}_{focus_rule_id}", fmt=plot_fmt
                            ),
                            key=f"fig_top_{device}_{focus_rule_id}",
                        )
                    else:
                        miss = list(getattr(focus_res, "missing_roles", None) or [])
                        note = str(getattr(focus_res, "notes", "") or "")
                        bits = [f"status `{status}`"]
                        if miss:
                            bits.append("missing: " + ", ".join(miss))
                        if note:
                            bits.append(note[:200])
                        st.info("No Plotly series for this rule — " + " · ".join(bits))
            else:
                focus_rule_id = None
                st.info("No applicable cookbook rules for this equipment type.")

            sens = sensor_fault_summary(plot_df, device_results, equipment_id=device)
            if not sens.empty:
                with st.expander("Sensor fault summary statistics", expanded=False):
                    st.caption(
                        "Mean/std/min/p50/max for sensors involved in FAULT sensor-validation rules."
                    )
                    st.dataframe(sens, width="stretch", height=220)
                    st.download_button(
                        "Download sensor fault stats CSV",
                        to_csv_bytes(sens),
                        f"{device}_sensor_fault_stats.csv",
                        key=f"dl_sens_{device}",
                    )

            st.markdown("##### Rule cards (catalog parity)")
            status_filter = st.radio(
                "Filter cards",
                ["All", "FAULT", "PASS", "SKIPPED", "Not run"],
                horizontal=True,
                index=0,
                key=f"plot_status_filter_{device}",
            )

            from app.rcx_plots import rcx_preset_coverage

            try:
                rcx_cov = rcx_preset_coverage(
                    frames,
                    st.session_state.role_map,
                    weather=st.session_state.weather,
                    schedule=OccupancySchedule.from_dict(
                        st.session_state.get("occupancy_schedule")
                    ),
                    comfort_low_f=float(st.session_state.get("zone_lo_f", 70.0)),
                    comfort_high_f=float(st.session_state.get("zone_hi_f", 75.0)),
                )
            except Exception:
                rcx_cov = pd.DataFrame()
            has_sens_fault = not sens.empty

            cards_shown = 0
            for rule in applicable:
                res = lookup.get((device, rule.id))
                card = build_rule_card(
                    equipment_id=device,
                    rule=rule,
                    result=res,
                    role_map=st.session_state.role_map,
                    mapped_df=plot_df,
                    params=st.session_state.get("params") or {},
                    results=st.session_state.batch_results,
                    rcx_coverage=rcx_cov if not rcx_cov.empty else None,
                    weather=st.session_state.weather,
                    has_sensor_fault_summary=has_sens_fault,
                )
                bucket = filter_status_bucket(card.status)
                if status_filter != "All" and bucket != status_filter:
                    continue
                cards_shown += 1
                title = f"{card.rule_id} — {card.title} · {card.status}"
                with st.expander(title, expanded=(rule.id == focus_rule_id)):
                    if card.description:
                        st.markdown(f"**Summary:** {card.description}")
                    if card.equation:
                        st.markdown(f"**Equation:** {card.equation}")
                    fh = card.fault_hours
                    meta_bits = [f"`{card.status}`"]
                    if fh is not None:
                        meta_bits.append(f"fault hours: {fh:.2f}")
                    if card.coverage_pct is not None:
                        meta_bits.append(
                            f"required roles: {card.required_roles_present}/{card.required_roles_total}"
                        )
                    if card.missing_roles:
                        meta_bits.append(f"missing: {', '.join(card.missing_roles)}")
                    st.caption(" · ".join(meta_bits))
                    if card.notes:
                        st.caption(card.notes)

                    st.markdown("**Rule facts**")
                    facts = list(card.catalog_facts) + [
                        ("Status", card.status),
                        (
                            "Fault hours",
                            "—" if card.fault_hours is None else f"{card.fault_hours:.2f}",
                        ),
                    ]
                    st.dataframe(
                        pd.DataFrame(facts, columns=["Field", "Value"]),
                        hide_index=True,
                        width="stretch",
                    )

                    st.markdown("**Points → Haystack tags**")
                    if card.points_note:
                        st.caption(card.points_note)
                    if card.mapping_rows:
                        map_df = pd.DataFrame(
                            [
                                {
                                    "role": m.role,
                                    "haystack": m.haystack_tag,
                                    "csv_column": m.csv_column,
                                    "requirement": m.requirement,
                                    "in_history": "yes" if m.in_history else "MISSING",
                                }
                                for m in card.mapping_rows
                            ]
                        )
                        st.dataframe(map_df, hide_index=True, width="stretch")
                    else:
                        st.caption("Sensor/control sweep — applies to present sensors / outputs.")

                    st.markdown("**Plot series**")
                    for bullet in card.plot_series:
                        st.markdown(f"- {bullet}")

                    st.markdown("**Sliders (tune params)**")
                    if card.param_rows:
                        st.dataframe(
                            pd.DataFrame(
                                [
                                    {
                                        "key": p.key,
                                        "label": p.label,
                                        "unit": p.unit,
                                        "value": p.value,
                                        "default": p.default,
                                        "min": p.min,
                                        "max": p.max,
                                        "step": p.step,
                                        "source": p.source,
                                    }
                                    for p in card.param_rows
                                ]
                            ),
                            hide_index=True,
                            width="stretch",
                        )
                    else:
                        st.caption("No tune params for this rule.")

                    st.markdown("**Analytics / related views**")
                    st.caption(card.analytics_hint or "—")
                    for line in card.analytics_fit:
                        st.markdown(f"- {line}")

                    if rule.id == focus_rule_id:
                        st.caption("Chart for this rule is in the **panel above**.")

            if cards_shown == 0:
                st.info(f"No cards match filter **{status_filter}**.")
            else:
                st.caption(
                    f"{cards_shown} card(s) · {len(applicable)} applicable rules · "
                    f"traces ≤ {max_plot_points():,} pts"
                )

    if section == "RCx Plots":
        try:
            render_rcx_plots_tab(
                frames,
                st.session_state.role_map,
                weather=st.session_state.weather,
                unit_system=st.session_state.get("unit_system", "imperial"),
                occupancy_schedule=st.session_state.get("occupancy_schedule"),
                zone_lo_f=float(st.session_state.get("zone_lo_f", 70.0)),
                zone_hi_f=float(st.session_state.get("zone_hi_f", 75.0)),
            )
        except Exception as exc:
            st.error(f"RCx Plots failed: {exc}")

    if section == "Metering":
        st.subheader("Metering")
        st.caption(
            "Building / plant electrical and gas meters vs degree-days (web OAT). "
            "Same rollups as RCx metering presets at the end of **RCx Plots** — this section starts "
            "the dedicated Metering category (expand later)."
        )
        from app.metering import build_meter_monthly_table, meter_scatter_frame

        for kind, title, dd_label in (
            ("electric", "Electric (kWh) vs CDD", "CDD"),
            ("gas", "Natural gas vs HDD", "HDD"),
        ):
            st.markdown(f"##### {title}")
            monthly, stats, reason = build_meter_monthly_table(
                frames,
                st.session_state.role_map,
                kind=kind,  # type: ignore[arg-type]
                weather=st.session_state.weather,
            )
            if reason or monthly.empty:
                st.info(reason or "No meter series for this package.")
                continue
            energy_col = "kwh" if kind == "electric" else "gas_qty"
            bar = monthly_energy_bar(
                monthly,
                energy_col=energy_col,
                title=f"Monthly {energy_col} by meter",
            )
            if bar is not None:
                st.plotly_chart(
                    bar,
                    width="stretch",
                    config=plotly_config(filename=f"meter_{kind}_bar"),
                    key=f"meter_{kind}_bar",
                )
            scatter_df = meter_scatter_frame(monthly, kind=kind)  # type: ignore[arg-type]
            scat = energy_degree_day_scatter(
                scatter_df,
                x_title=dd_label,
                y_title=energy_col,
                title=f"{title} scatter",
            )
            if scat is not None:
                st.plotly_chart(
                    scat,
                    width="stretch",
                    config=plotly_config(filename=f"meter_{kind}_scatter"),
                    key=f"meter_{kind}_scatter",
                )
            if stats is not None and not stats.empty:
                st.dataframe(stats, hide_index=True, width="stretch")
            st.download_button(
                f"Download {kind} monthly CSV",
                to_csv_bytes(monthly),
                f"meter_{kind}_monthly.csv",
                key=f"dl_meter_{kind}",
            )

    if section == "Export":
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

        st.markdown("##### DOCX reports")
        st.caption(
            "FDD equation template lives on **FDD Plots** only. Export keeps data-model / RCx / analytics Word files."
        )
        try:
            from app.data_model_tree import build_data_model_tree
            from app.docx_report import (
                build_analytics_docx,
                build_building_data_model_docx,
                build_rcx_catalog_docx,
            )
            from app.rcx_plots import rcx_preset_coverage

            tree = build_data_model_tree(
                frames,
                st.session_state.role_map,
                building_id=st.session_state.get("building_id") or "",
                vav_to_ahu=st.session_state.get("vav_to_ahu")
                or (st.session_state.get("package_report") or {}).get("vav_to_ahu"),
            )
            st.download_button(
                "Download RCx catalog DOCX",
                data=build_rcx_catalog_docx(
                    building_id=st.session_state.get("building_id") or "",
                    frames=frames,
                    role_map=st.session_state.role_map,
                    weather=st.session_state.weather,
                    results=st.session_state.batch_results,
                    params=st.session_state.get("params") or {},
                    zone_lo_f=float(st.session_state.get("zone_lo_f", 70.0)),
                    zone_hi_f=float(st.session_state.get("zone_hi_f", 75.0)),
                    occupancy_schedule=st.session_state.get("occupancy_schedule"),
                    unit_system=st.session_state.get("unit_system", "imperial"),
                    motor_weekly=motor_weekly if isinstance(motor_weekly, pd.DataFrame) else None,
                    cool_bins=cool_bins if isinstance(cool_bins, pd.DataFrame) else None,
                ),
                file_name="rcx_catalog_report.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key="dl_export_rcx_catalog_docx",
            )
            st.download_button(
                "Download data_model.docx",
                data=build_building_data_model_docx(tree),
                file_name="data_model.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key="dl_export_data_model_docx",
            )
            rcx = rcx_preset_coverage(
                frames, st.session_state.role_map, weather=st.session_state.weather
            )
            # Prefer already-computed analytics frames when visiting Overview/Analytics first
            _mw = motor_weekly if isinstance(motor_weekly, pd.DataFrame) else pd.DataFrame()
            _cb = cool_bins if isinstance(cool_bins, pd.DataFrame) else pd.DataFrame()
            st.download_button(
                "Download analytics.docx",
                data=build_analytics_docx(
                    building_id=st.session_state.get("building_id") or "",
                    motor_weekly=_mw,
                    cool_bins=_cb,
                    rcx_coverage=rcx,
                    tree=tree,
                ),
                file_name="analytics.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key="dl_export_analytics_docx",
            )
        except Exception as exc:
            st.warning(f"DOCX exports unavailable: {exc}")


if __name__ == "__main__":
    main()
