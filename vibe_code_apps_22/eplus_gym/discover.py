"""Discover EnergyPlus / pyenergyplus on Windows or Linux."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional


def energyplus_root_candidates() -> list[Path]:
    env = os.environ.get("ENERGYPLUS_ROOT") or os.environ.get("EPLUS_ROOT")
    roots: list[Path] = []
    if env:
        roots.append(Path(env))
    # Common install locations
    roots.extend(
        [
            Path(r"C:\EnergyPlusV24-2-0"),
            Path(r"C:\EnergyPlusV24-1-0"),
            Path(r"C:\EnergyPlusV23-2-0"),
            Path(r"C:\EnergyPlusV22-2-0"),
            Path("/usr/local/EnergyPlus-24-2-0"),
            Path("/usr/local/EnergyPlus-23-2-0"),
        ]
    )
    # Also scan C:\ for EnergyPlusV*
    drive = Path("C:/")
    if drive.is_dir():
        try:
            for p in sorted(drive.glob("EnergyPlusV*"), reverse=True):
                roots.append(p)
        except OSError:
            pass
    # de-dupe preserving order
    seen: set[str] = set()
    out: list[Path] = []
    for r in roots:
        key = str(r.resolve()) if r.exists() else str(r)
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def try_import_energyplus_api():
    """Return (EnergyPlusAPI, DataExchange, root) or raise ImportError."""
    last_err: Optional[Exception] = None
    for root in energyplus_root_candidates():
        if not root.is_dir():
            continue
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        try:
            from pyenergyplus.api import EnergyPlusAPI  # type: ignore

            api = EnergyPlusAPI()
            return EnergyPlusAPI, api.exchange, root
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            continue
    # bare import (PYTHONPATH already set)
    try:
        from pyenergyplus.api import EnergyPlusAPI  # type: ignore

        api = EnergyPlusAPI()
        return EnergyPlusAPI, api.exchange, None
    except Exception as exc:  # noqa: BLE001
        last_err = exc
    raise ImportError(
        "pyenergyplus not found. Install EnergyPlus 9.3+ and set ENERGYPLUS_ROOT "
        f"or PYTHONPATH. Last error: {last_err}"
    )


def energyplus_available() -> bool:
    try:
        try_import_energyplus_api()
        return True
    except ImportError:
        return False
