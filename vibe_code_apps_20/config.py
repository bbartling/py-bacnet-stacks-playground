"""Load Sketchbox credentials from vibe_code_apps_20/.env (or process env)."""

from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def load_dotenv(path: Path | None = None) -> Path | None:
    """Minimal .env loader (no python-dotenv dependency)."""
    p = path or (ROOT / ".env")
    if not p.is_file():
        return None
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val
    return p


def sketchbox_creds() -> dict[str, str]:
    load_dotenv()
    email = (os.environ.get("SKETCHBOX_EMAIL") or "").strip()
    password = (os.environ.get("SKETCHBOX_PASSWORD") or "").strip()
    base = (os.environ.get("SKETCHBOX_BASE_URL") or "https://www.sketchbox.io").rstrip("/")
    return {
        "email": email,
        "password": password,
        "base_url": base,
        "headed": (os.environ.get("SKETCHBOX_HEADED") or "1").strip() not in {"0", "false", "no"},
        "slow_mo_ms": int(float(os.environ.get("SKETCHBOX_SLOW_MO_MS") or "50")),
    }
