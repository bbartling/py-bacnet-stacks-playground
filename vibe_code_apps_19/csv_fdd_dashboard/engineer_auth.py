"""Single-engineer PIN auth and package lock for read-only delivery."""

from __future__ import annotations

import os
from typing import Any


def engineer_pin() -> str:
    return os.environ.get("ENGINEER_PIN", "vibe-coder").strip()


def is_engineer(session: dict[str, Any]) -> bool:
    return bool(session.get("engineer_logged_in"))


def is_locked(session: dict[str, Any]) -> bool:
    return bool(session.get("package_locked"))


def can_edit(session: dict[str, Any]) -> bool:
    if is_engineer(session):
        return True
    return not is_locked(session)


def login(session: dict[str, Any], pin: str) -> bool:
    if pin.strip() == engineer_pin():
        session["engineer_logged_in"] = True
        return True
    return False


def logout(session: dict[str, Any]) -> None:
    session["engineer_logged_in"] = False


def lock_package(session: dict[str, Any]) -> None:
    session["package_locked"] = True


def session_flags(session: dict[str, Any]) -> dict[str, Any]:
    return {
        "engineer": is_engineer(session),
        "locked": is_locked(session),
        "can_edit": can_edit(session),
    }
