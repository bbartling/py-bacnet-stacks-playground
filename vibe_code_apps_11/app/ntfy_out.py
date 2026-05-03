"""Push notifications via ntfy (https://ntfy.sh) — same pattern as Invoke-RestMethod -Uri https://ntfy.sh/$Topic."""
from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

import requests

from app.config import settings


def send_ntfy(
    message: str,
    *,
    title: str = "diy-bas",
    topic: str | None = None,
    priority: str = "default",
    tags: str = "",
    base_url: str | None = None,
    username: str | None = None,
    password: str | None = None,
    timeout_sec: float | None = None,
) -> dict[str, Any]:
    """
    POST message body to ``{base}/{topic}`` with ntfy headers (Title, Priority, Tags).

    ``priority`` is passed through (e.g. ``min``, ``low``, ``default``, ``high``, ``max`` or ``1``–``5``).
    """
    if not settings.ntfy_allowed:
        raise ValueError("ntfy is disabled (set DIY_BAS_NTFY_ALLOWED=true in .env and restart)")
    base = (base_url or settings.ntfy_url or "https://ntfy.sh").rstrip("/")
    t = (topic or settings.ntfy_topic or "").strip()
    if not t:
        raise ValueError("ntfy topic is empty (set DIY_BAS_NTFY_TOPIC or pass topic)")
    url = f"{base}/{quote(t, safe='')}"
    headers: dict[str, str] = {
        "Title": title[:200] if title else "diy-bas",
        "Priority": str(priority or "default"),
    }
    tags_s = (tags or "").strip()
    if tags_s:
        headers["Tags"] = tags_s[:200]
    user = (username if username is not None else settings.ntfy_username or "").strip()
    pwd = password if password is not None else settings.ntfy_password
    auth: tuple[str, str] | None = None
    if user:
        auth = (user, pwd or "")
    to = float(timeout_sec or settings.ntfy_timeout_sec or 15)
    r = requests.post(
        url,
        data=(message or " ").encode("utf-8"),
        headers=headers,
        auth=auth,
        timeout=max(5.0, min(60.0, to)),
    )
    r.raise_for_status()
    text = (r.text or "").strip()
    if text.startswith("{") or text.startswith("["):
        try:
            parsed: Any = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    return {"ok": True, "status": r.status_code, "body": text[:2000]}


def send_test_schedule_style(message: str | None = None) -> dict[str, Any]:
    """Convenience: BAS-style title/tags like the PowerShell example."""
    msg = (message or "Schedule / BAS test notification from diy-bas.").strip()
    return send_ntfy(
        msg,
        title="BAS Alarm",
        priority="high",
        tags="warning",
    )
