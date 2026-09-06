"""Load ENERGYPLUS_* paths from .env (Windows / Linux / macOS)."""
from __future__ import annotations

import os
from pathlib import Path

from .residential.model import PACKAGE_ROOT

_ENV_KEYS = (
    "ENERGYPLUS_EXE",
    "ENERGYPLUS_ROOT",
    "ENERGYPLUS_WEATHER",
    "ENERGYPLUS_WEATHER_DIR",
    "EPLUS_WORKER_URL",
    "EPLUS_WORKER_API_KEY",
    "EPLUS_BACKEND",
    "EPLUS_WORKER_FORCE",
)


def env_file_candidates() -> tuple[Path, ...]:
    cwd = Path.cwd()
    home_worker = Path.home() / "Documents" / "vibe23-energyplus-worker" / ".env.render.local"
    return (
        cwd / ".env",
        cwd / ".env.local",
        PACKAGE_ROOT / ".env",
        PACKAGE_ROOT / ".env.local",
        home_worker,
    )


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse KEY=VALUE lines; quotes stripped; comments ignored."""
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.lower().startswith("export "):
            line = line[7:].strip()
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key:
            out[key] = value
    return out


def load_energyplus_env(*, override: bool = False) -> dict[str, str]:
    """Populate os.environ from .env candidates (does not override by default).

    Scans all candidates so ENERGYPLUS_* and EPLUS_WORKER_* can come from
    different files (e.g. package ``.env`` + worker ``.env.render.local``).
    """
    loaded: dict[str, str] = {}
    for path in env_file_candidates():
        parsed = parse_env_file(path)
        if not parsed:
            continue
        for key, value in parsed.items():
            if key not in _ENV_KEYS:
                continue
            if override or not os.environ.get(key):
                os.environ[key] = value
            loaded[key] = os.environ.get(key, value)
    for key in _ENV_KEYS:
        if os.environ.get(key):
            loaded[key] = os.environ[key]
    return loaded


def energyplus_unix_roots() -> tuple[Path, ...]:
    home = Path.home()
    return (
        Path("/usr/local"),
        Path("/opt"),
        Path("/usr"),
        home / "EnergyPlus",
        home / ".local",
        Path("/Applications"),
    )


def default_energyplus_executables() -> list[Path]:
    """Common native EnergyPlus 26.1 install locations on Windows, Linux, and macOS."""
    names = ("energyplus", "energyplus.exe")
    roots = [
        Path(r"C:\EnergyPlusV26-1-0"),
        Path(r"C:\EnergyPlusV25-1-0"),
        Path("/usr/local/EnergyPlus-26-1-0"),
        Path("/usr/local/EnergyPlus-25-1-0"),
        Path("/opt/EnergyPlus-26-1-0"),
        Path("/Applications/EnergyPlus-26-1-0"),
        Path.home() / "EnergyPlus-26-1-0",
    ]
    out: list[Path] = []
    for root in roots:
        for name in names:
            out.append(root / name)
    for base in energyplus_unix_roots():
        if not base.exists():
            continue
        try:
            for child in base.iterdir():
                if "energyplus" not in child.name.lower():
                    continue
                for name in names:
                    out.append(child / name)
        except OSError:
            continue
    return out
