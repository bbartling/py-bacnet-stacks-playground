"""Environment freeze + A04 fail-closed for nightly grid compute."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from eplus_gym.a04_identity import A04_IDF_NAME, A04_SHA_CRLF
from eplus_gym.rl.nightly_grid_menu import build_one_day_menu, load_nightly_contract, menu_sha256
from eplus_gym.site_pins import resolve_site_epw, sha256_file

PUBLIC_LABELS = [
    "SIMULATION-ONLY RESEARCH",
    "A04 IS NOT A TRANSIENT-VALIDATED PHYSICS CHAMPION",
    "VERIFIED BAS INCUMBENT REMAINS UNRESOLVED",
    "RETROSPECTIVE WEATHER BENCHMARK",
    "NOT VALIDATED FOR OPERATIONAL DSM",
    "NO BACNET COMMAND AUTHORITY",
]


class A04HashMismatchError(RuntimeError):
    """A04 IDF bytes do not match the frozen champion hash."""


def _cpu_model() -> str | None:
    try:
        if sys.platform == "win32":
            out = subprocess.check_output(
                ["wmic", "cpu", "get", "Name"], text=True, stderr=subprocess.DEVNULL, timeout=10
            )
            lines = [ln.strip() for ln in out.splitlines() if ln.strip() and ln.strip().lower() != "name"]
            return lines[0] if lines else None
    except Exception:  # noqa: BLE001
        return None
    return platform.processor() or None


def _ram_bytes() -> int | None:
    try:
        import psutil

        return int(psutil.virtual_memory().total)
    except Exception:  # noqa: BLE001
        return None


def _core_counts() -> dict[str, Any]:
    try:
        import psutil

        return {
            "physical_cores": psutil.cpu_count(logical=False),
            "logical_cores": psutil.cpu_count(logical=True),
        }
    except Exception:  # noqa: BLE001
        return {"physical_cores": None, "logical_cores": os.cpu_count()}


def _git_state(app_root: Path) -> dict[str, Any]:
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(app_root), text=True, stderr=subprocess.DEVNULL
        ).strip()
        dirty = (
            subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=str(app_root), text=True, stderr=subprocess.DEVNULL
            ).strip()
            != ""
        )
        return {"git_sha": sha, "dirty_tree": dirty}
    except Exception as exc:  # noqa: BLE001
        return {"git_sha": None, "dirty_tree": None, "reason": str(exc)}


def assert_a04_hash(idf: Path, *, expected_full: str | None = None, prefix: str | None = None) -> str:
    digest = sha256_file(idf)
    exp = expected_full or A04_SHA_CRLF
    pref = prefix or exp[:16]
    if not digest.startswith(pref) and digest != exp:
        # Allow LF-normalized mismatch only if prefix of CRLF expected fails hard
        raise A04HashMismatchError(
            f"A04 hash mismatch: got {digest[:16]}… expected prefix {pref} (full {exp[:16]}…)"
        )
    if digest != exp and not digest.startswith(pref):
        raise A04HashMismatchError(f"A04 hash mismatch: {digest} != {exp}")
    # Prefer exact match; if only prefix matches (line-ending variant), still fail closed per plan
    if digest != exp:
        raise A04HashMismatchError(
            f"A04 SHA-256 {digest} does not equal frozen {exp}; refusing A05/alternate IDF"
        )
    return digest


def build_environment_manifest(*, app_root: Path, site: Path) -> dict[str, Any]:
    contract = load_nightly_contract(app_root)
    idf = Path(app_root) / "models" / "eplus" / A04_IDF_NAME
    epw = resolve_site_epw(site)
    idf_sha = assert_a04_hash(
        idf,
        expected_full=contract.get("a04_sha256_expected_full") or A04_SHA_CRLF,
        prefix=contract.get("a04_sha256_prefix_required"),
    )
    day = str(contract["primary_benchmark_day"])
    menu = build_one_day_menu(day=day)
    fixtures = Path(app_root) / "contracts" / "fixtures" / "tariffs"
    cores = _core_counts()
    git = _git_state(app_root)
    return {
        "schema": "vibe22.nightly_grid_environment.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "public_labels": PUBLIC_LABELS,
        "idf": {"path": str(idf), "sha256": idf_sha},
        "epw": {"path": str(epw), "sha256": sha256_file(epw)},
        "energyplus_version": contract.get("energyplus_version"),
        "candidate_menu_sha256": menu_sha256(menu),
        "declared_action_count": menu["declared_action_count"],
        "n_unique_one_day": menu["n_unique_one_day"],
        "reward_contract": contract.get("reward_contract"),
        "action_contract_version": contract.get("action_contract_version"),
        "baseline_contract": contract.get("paired_baseline"),
        "baseline_contract_sha256": sha256_file(Path(app_root) / "contracts" / "observed_bas_incumbent_v2.json"),
        "tariff_fixtures": {
            p.name: sha256_file(p) for p in sorted(fixtures.glob("*.json")) if p.is_file()
        },
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "cpu_model": _cpu_model(),
        **cores,
        "installed_ram_bytes": _ram_bytes(),
        "python_version": sys.version.split()[0],
        **git,
        "primary_benchmark_day": day,
        "lookback_day": contract["lookback_day"],
        "bacnet_command_authority": 0,
    }


def build_provenance(*, app_root: Path, site: Path, env: dict[str, Any] | None = None) -> dict[str, Any]:
    env = env or build_environment_manifest(app_root=app_root, site=site)
    contract = load_nightly_contract(app_root)
    return {
        "schema": "vibe22.nightly_grid_provenance.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contract": contract,
        "environment": env,
        "selection_wording": contract.get("selection_wording"),
        "public_labels": PUBLIC_LABELS,
    }


def build_artifact_hashes(*, app_root: Path, site: Path, env: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """SHA-256 pins for reward, action, baseline, menu, tariffs, IDF, EPW."""
    app = Path(app_root)
    env = env or build_environment_manifest(app_root=app, site=Path(site))
    reward_py = app / "eplus_gym" / "rl" / "reward_v2.py"
    reward_json = app / "contracts" / "reward_contract_v2.json"
    action_py = app / "eplus_gym" / "rl" / "research_spaces.py"
    return {
        "schema": "vibe22.nightly_grid_artifact_hashes.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reward_v2_implementation_sha256": sha256_file(reward_py),
        "reward_contract_v2_sha256": sha256_file(reward_json),
        "research_action_contract_v3_implementation_sha256": sha256_file(action_py),
        "baseline_contract_sha256": env.get("baseline_contract_sha256"),
        "candidate_menu_sha256": env.get("candidate_menu_sha256"),
        "tariff_fixtures": env.get("tariff_fixtures") or {},
        "a04_idf_sha256": (env.get("idf") or {}).get("sha256"),
        "epw_sha256": (env.get("epw") or {}).get("sha256"),
    }
