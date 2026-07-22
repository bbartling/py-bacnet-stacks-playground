"""Agent → Streamlit Studio bootstrap (no HTTP API).

After headless ``publish_run_for_studio`` / calibrate-campaign, write
``studio_bootstrap.json`` under the shared workspace so the next Streamlit
start auto-loads Fuel + Twin without Uploads / Refresh clicks.

Resolve order:
1. ``WATTLAB_STUDIO_BOOTSTRAP`` env (absolute file path)
2. ``$WATTLAB_STUDIO_WORKSPACE/studio_bootstrap.json``
3. ``$WATTLAB_STUDIO_WORKSPACE/.last_studio_session.json``

Disable: ``WATTLAB_STUDIO_BOOTSTRAP_DISABLE=1``
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

BOOTSTRAP_VERSION = 1
DEFAULT_BOOTSTRAP_NAME = "studio_bootstrap.json"
FALLBACK_BOOTSTRAP_NAME = ".last_studio_session.json"
_KNOWN_KEYS = frozenset(
    {
        "version",
        "energy_campus_dir",
        "dump_zip",
        "preferred_run_id",
        "answers_path",
        "ecm_scenario_path",
        "auto_refresh_runs",
        "notes",
    }
)
_CONTENT_KEYS = (
    "energy_campus_dir",
    "dump_zip",
    "preferred_run_id",
    "answers_path",
)


def bootstrap_disabled() -> bool:
    return (os.environ.get("WATTLAB_STUDIO_BOOTSTRAP_DISABLE") or "").strip() in {
        "1",
        "true",
        "True",
        "yes",
        "YES",
    }


def bootstrap_file_mtime(path: Path | str | None) -> float | None:
    """Return file mtime, or None if missing."""
    if path is None:
        return None
    p = Path(path)
    try:
        return float(p.stat().st_mtime) if p.is_file() else None
    except OSError:
        return None


def validate_bootstrap_payload(payload: dict[str, Any] | None) -> list[str]:
    """Return soft warnings (never hard-fail). Empty list = looks fine."""
    warnings: list[str] = []
    if not isinstance(payload, dict):
        return ["bootstrap payload is not an object"]
    ver = payload.get("version")
    if ver is None:
        warnings.append("version missing (expected 1)")
    elif ver != BOOTSTRAP_VERSION:
        warnings.append(f"version={ver!r} (expected {BOOTSTRAP_VERSION})")
    unknown = sorted(set(payload) - _KNOWN_KEYS)
    if unknown:
        warnings.append(f"unknown keys: {', '.join(unknown)}")
    if not any(payload.get(k) for k in _CONTENT_KEYS):
        warnings.append(
            "empty bootstrap — set energy_campus_dir, dump_zip, preferred_run_id, and/or answers_path"
        )
    return warnings


def upsert_bootstrap_preferred_run(
    run_id: str,
    *,
    workspace: Path | None = None,
) -> Path | None:
    """Merge ``preferred_run_id`` into studio_bootstrap.json (best-effort).

    Creates a minimal file when missing. No-op when bootstrap is disabled.
    Never raises for callers — returns written path or None.
    """
    if bootstrap_disabled() or not run_id:
        return None
    try:
        from datetime import datetime, timezone

        from wattlab.studio.workspace import ensure_workspace

        root = Path(workspace) if workspace is not None else ensure_workspace()
        path = root / DEFAULT_BOOTSTRAP_NAME
        payload: dict[str, Any] = {}
        if path.is_file():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    payload = dict(raw)
            except (OSError, json.JSONDecodeError):
                payload = {}
        payload["version"] = BOOTSTRAP_VERSION
        payload["preferred_run_id"] = str(run_id)
        payload["auto_refresh_runs"] = bool(payload.get("auto_refresh_runs", True))
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        stamp_line = f"preferred_run_id upserted by publish_run_for_studio @ {stamp}"
        prev = str(payload.get("notes") or "").strip()
        if prev and stamp_line not in prev:
            payload["notes"] = f"{prev}\n{stamp_line}"
        elif not prev:
            payload["notes"] = stamp_line
        # else: stamp already present — leave notes unchanged
        write_bootstrap(payload, path=path, also_fallback=True)
        return path
    except Exception:  # noqa: BLE001
        return None


def resolve_bootstrap_path(workspace: Path | None = None) -> Path | None:
    """Return bootstrap file to apply, or None if missing / disabled."""
    if bootstrap_disabled():
        return None
    env = (os.environ.get("WATTLAB_STUDIO_BOOTSTRAP") or "").strip()
    if env:
        p = Path(env).expanduser()
        return p if p.is_file() else None
    from wattlab.studio.workspace import workspace_root

    root = Path(workspace) if workspace is not None else workspace_root()
    for name in (DEFAULT_BOOTSTRAP_NAME, FALLBACK_BOOTSTRAP_NAME):
        p = root / name
        if p.is_file():
            return p
    return None


def build_bootstrap_payload(
    *,
    energy_campus_dir: str | Path | None = None,
    dump_zip: str | Path | None = None,
    preferred_run_id: str | None = None,
    answers_path: str | Path | None = None,
    auto_refresh_runs: bool = True,
    notes: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "version": BOOTSTRAP_VERSION,
        "auto_refresh_runs": bool(auto_refresh_runs),
        "notes": notes
        or "Written by agent after publish_run_for_studio for Studio auto-load",
    }
    if energy_campus_dir:
        payload["energy_campus_dir"] = str(energy_campus_dir)
    if dump_zip:
        payload["dump_zip"] = str(dump_zip)
    if preferred_run_id:
        payload["preferred_run_id"] = str(preferred_run_id)
    if answers_path:
        payload["answers_path"] = str(answers_path)
    return payload


def write_bootstrap(
    payload: dict[str, Any],
    *,
    path: str | Path | None = None,
    also_fallback: bool = True,
) -> list[Path]:
    """Write bootstrap JSON under the Studio workspace."""
    from wattlab.studio.workspace import ensure_workspace

    root = ensure_workspace()
    if payload.get("version") != BOOTSTRAP_VERSION:
        payload = {**payload, "version": BOOTSTRAP_VERSION}
    targets: list[Path] = []
    if path is not None:
        targets.append(Path(path))
    else:
        targets.append(root / DEFAULT_BOOTSTRAP_NAME)
    if also_fallback:
        fb = root / FALLBACK_BOOTSTRAP_NAME
        if fb not in targets:
            targets.append(fb)
    written: list[Path] = []
    text = json.dumps(payload, indent=2)
    for t in targets:
        t.parent.mkdir(parents=True, exist_ok=True)
        t.write_text(text, encoding="utf-8")
        written.append(t)
    return written


def _resolve_under_workspace(root: Path, rel: str | None) -> Path | None:
    if not rel:
        return None
    p = Path(rel)
    if not p.is_absolute():
        p = root / p
    return p if p.exists() else None


def _ss_get(session_state: Any, key: str, default: Any = None) -> Any:
    """Read session_state without triggering Streamlit's ``__getattr__`` for ``.get``."""
    try:
        if key in session_state:
            return session_state[key]
    except TypeError:
        pass
    if isinstance(session_state, dict):
        return session_state.get(key, default)
    try:
        return session_state[key]
    except (KeyError, AttributeError, TypeError):
        return default


def _ss_set(session_state: Any, key: str, value: Any) -> None:
    session_state[key] = value


def apply_bootstrap_to_session(
    session_state: Any,
    *,
    workspace: Path | None = None,
) -> dict[str, Any]:
    """Load campus / dump / preferred run into Streamlit session_state.

    Idempotent when ``session_state["_studio_bootstrapped"]`` is already set.
    Never raises on missing paths — returns NEEDS_INPUT notes instead.
    """
    result: dict[str, Any] = {
        "applied": False,
        "banner": None,
        "needs_input": [],
        "errors": [],
        "warnings": [],
    }
    if _ss_get(session_state, "_studio_bootstrapped"):
        result["skipped"] = "already_bootstrapped"
        return result

    path = resolve_bootstrap_path(workspace)
    if path is None:
        result["skipped"] = "no_bootstrap_file"
        return result

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        result["errors"].append(f"bootstrap unreadable: {exc}")
        _ss_set(session_state, "_studio_bootstrapped", True)
        _ss_set(session_state, "_studio_bootstrap_path", str(path))
        _ss_set(session_state, "_studio_bootstrap_applied_mtime", bootstrap_file_mtime(path))
        return result

    if not isinstance(payload, dict):
        result["errors"].append("bootstrap payload is not an object")
        _ss_set(session_state, "_studio_bootstrapped", True)
        return result

    result["warnings"] = validate_bootstrap_payload(payload)

    from wattlab.studio.workspace import ensure_workspace, runs_dir

    root = Path(workspace) if workspace is not None else ensure_workspace()
    notes: list[str] = []

    campus_rel = payload.get("energy_campus_dir")
    campus_path = _resolve_under_workspace(root, campus_rel)
    if campus_rel and campus_path is None:
        result["needs_input"].append(f"energy_campus_dir missing: {campus_rel}")
    elif campus_path is not None:
        try:
            from wattlab.energy_use import load_energy_use_package

            load_target = campus_path
            if campus_path.is_file() and campus_path.name == "campus.json":
                load_target = campus_path.parent
            pkg = load_energy_use_package(load_target)
            _ss_set(session_state, "studio_energy", pkg)
            _ss_set(session_state, "studio_campus", pkg.campus)
            notes.append(f"Fuel campus ← {campus_rel}")
        except Exception as exc:  # noqa: BLE001
            result["needs_input"].append(f"campus load failed: {exc}")

    dump_rel = payload.get("dump_zip")
    dump_path = _resolve_under_workspace(root, dump_rel)
    if dump_rel and dump_path is None:
        result["needs_input"].append(f"dump_zip missing: {dump_rel}")
    elif dump_path is not None:
        try:
            from wattlab.seed import load_bundle

            bundle = load_bundle(dump_path)
            _ss_set(session_state, "studio_bundle", bundle)
            notes.append(f"Twin dump ← {dump_rel}")
        except Exception as exc:  # noqa: BLE001
            result["needs_input"].append(f"dump load failed: {exc}")

    answers_rel = payload.get("answers_path")
    answers_path = _resolve_under_workspace(root, answers_rel)
    if answers_rel and answers_path is None:
        result["needs_input"].append(f"answers_path missing: {answers_rel}")
    elif answers_path is not None:
        try:
            _ss_set(
                session_state,
                "studio_answers",
                json.loads(answers_path.read_text(encoding="utf-8")),
            )
            notes.append(f"answers ← {answers_rel}")
        except Exception as exc:  # noqa: BLE001
            result["needs_input"].append(f"answers load failed: {exc}")

    ecm_rel = payload.get("ecm_scenario_path")
    ecm_path = _resolve_under_workspace(root, ecm_rel) if ecm_rel else None
    if ecm_rel and ecm_path is None:
        result["needs_input"].append(f"ecm_scenario_path missing: {ecm_rel}")
    elif ecm_path is not None:
        _ss_set(session_state, "studio_ecm_scenario_path", str(ecm_path))
        notes.append(f"ecm_scenario ← {ecm_rel}")

    if payload.get("auto_refresh_runs", True):
        rid = payload.get("preferred_run_id")
        run_dir: Path | None = None
        if rid:
            cand = runs_dir() / str(rid)
            if cand.is_dir():
                run_dir = cand
            else:
                result["needs_input"].append(f"preferred_run_id missing under runs/: {rid}")
        if run_dir is None:
            pointer = runs_dir() / "CURRENT_RUN.txt"
            if pointer.is_file():
                try:
                    p = Path(pointer.read_text(encoding="utf-8").strip())
                    if p.is_dir():
                        run_dir = p
                except OSError:
                    pass
        if run_dir is not None:
            _ss_set(session_state, "studio_active_run", str(run_dir.resolve()))
            notes.append(f"Twin run ← {run_dir.name}")

            # Prefer resolved_profile.json from the run when answers incomplete
            if not _ss_get(session_state, "studio_profile"):
                rp = run_dir / "resolved_profile.json"
                if rp.is_file():
                    try:
                        profile = json.loads(rp.read_text(encoding="utf-8"))
                        if isinstance(profile, dict) and profile:
                            _ss_set(session_state, "studio_profile", profile)
                            notes.append("studio_profile ← run resolved_profile.json")
                    except (OSError, json.JSONDecodeError):
                        pass

    # Promote answers → studio_profile so ECMs unlock without Twin form click
    answers = _ss_get(session_state, "studio_answers")
    if isinstance(answers, dict) and not _ss_get(session_state, "studio_profile"):
        try:
            from wattlab.studio.status import answers_complete, profile_minimal_from_answers
            from wattlab.defaults import resolve_profile

            if answers_complete(answers):
                profile = resolve_profile(profile_minimal_from_answers(answers))
                _ss_set(session_state, "studio_profile", profile)
                notes.append("studio_profile ← answers.json")
        except Exception as exc:  # noqa: BLE001
            result["warnings"].append(f"profile from answers skipped: {exc}")

    mtime = bootstrap_file_mtime(path)
    _ss_set(session_state, "_studio_bootstrapped", True)
    _ss_set(session_state, "_studio_bootstrap_path", str(path))
    _ss_set(session_state, "_studio_bootstrap_notes", notes)
    _ss_set(session_state, "_studio_bootstrap_applied_mtime", mtime)
    result["applied"] = True
    result["path"] = str(path)
    result["mtime"] = mtime
    result["notes"] = notes
    if notes or result["needs_input"]:
        result["banner"] = (
            f"Bootstrapped from {path.name}"
            + (f" — {'; '.join(notes)}" if notes else "")
        )
    else:
        result["banner"] = f"Bootstrapped from {path.name}"
    return result


def clear_bootstrap_session_flags(session_state: Any) -> None:
    """Clear once-per-session flags so Re-apply can run again."""
    for key in (
        "_studio_bootstrapped",
        "_studio_bootstrap_notes",
        "_studio_bootstrap_applied_mtime",
    ):
        try:
            if key in session_state:
                del session_state[key]
        except (KeyError, TypeError, AttributeError):
            if isinstance(session_state, dict):
                session_state.pop(key, None)


def main(argv: list[str] | None = None) -> int:
    """CLI: ``wattlab studio-bootstrap --campus … --dump … --run-id …``."""
    import argparse
    import sys

    p = argparse.ArgumentParser(
        description="Write studio_bootstrap.json for Streamlit auto-load"
    )
    p.add_argument("--campus", type=Path, default=None, help="energy campus dir or campus.json")
    p.add_argument("--dump", type=Path, default=None, help="dump zip or folder")
    p.add_argument("--run-id", type=str, default=None, help="preferred runs/<id>")
    p.add_argument("--answers", type=Path, default=None)
    p.add_argument("--notes", type=str, default="")
    p.add_argument("--out", type=Path, default=None, help="override bootstrap path")
    p.add_argument("--no-fallback", action="store_true")
    args = p.parse_args(argv)

    from wattlab.studio.workspace import ensure_workspace

    root = ensure_workspace()

    def _rel(path: Path | None) -> str | None:
        if path is None:
            return None
        path = path.resolve()
        try:
            return str(path.relative_to(root)).replace("\\", "/")
        except ValueError:
            return str(path)

    campus = args.campus
    if campus is not None and campus.is_file() and campus.name == "campus.json":
        campus = campus.parent

    payload = build_bootstrap_payload(
        energy_campus_dir=_rel(campus) if campus else None,
        dump_zip=_rel(args.dump) if args.dump else None,
        preferred_run_id=args.run_id,
        answers_path=_rel(args.answers) if args.answers else None,
        notes=args.notes,
    )
    if not any(
        payload.get(k)
        for k in ("energy_campus_dir", "dump_zip", "preferred_run_id", "answers_path")
    ):
        print(
            json.dumps({"ok": False, "error": "NEEDS_INPUT: pass --campus and/or --dump and/or --run-id"}),
            file=sys.stderr,
        )
        return 1
    written = write_bootstrap(
        payload, path=args.out, also_fallback=not args.no_fallback
    )
    print(json.dumps({"ok": True, "written": [str(w) for w in written], "payload": payload}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
