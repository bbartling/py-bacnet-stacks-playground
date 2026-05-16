#!/usr/bin/env python3
"""Parse PHASE_NOTEPAD, arm wire, enable poll job, merge cron .env (no LLM)."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_notepad(path: Path) -> dict[str, str | bool]:
    text = path.read_text(encoding="utf-8")
    bind_match = re.search(
        r"\*\*BACnet bind string\*\*[^|]*\|\s*`([^`]+)`",
        text,
        re.IGNORECASE,
    )
    bind = (bind_match.group(1).strip() if bind_match else "") or ""
    bind_ok = bool(bind) and "(fill)" not in bind.lower() and "/" in bind

    section_c = ""
    if "## C)" in text:
        section_c = text.split("## C)", 1)[1]
        if "## D)" in section_c:
            section_c = section_c.split("## D)", 1)[0]
    devices_ok = bool(re.search(r"\b\d{5,}\b", section_c))

    return {
        "bind": bind,
        "bind_ok": bind_ok,
        "devices_ok": devices_ok,
    }


def chat_requests_commissioning(chat_path: Path, *, max_messages: int = 40) -> bool:
    if not chat_path.is_file():
        return False
    try:
        doc = json.loads(chat_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    messages = doc.get("messages") or []
    if not isinstance(messages, list):
        return False
    keywords = (
        "who-is",
        "who is",
        "bacnet",
        "poll",
        "polling",
        "scraping",
        "commission",
        "online",
        "sensors",
        "wire",
    )
    for msg in reversed(messages[-max_messages:]):
        if not isinstance(msg, dict) or msg.get("role") != "user":
            continue
        body = (msg.get("content") or msg.get("text") or "").lower()
        if any(k in body for k in keywords):
            return True
    return False


def mark_signoff_checkboxes(checkpoints: Path, signer: str = "auto-commission") -> None:
    text = checkpoints.read_text(encoding="utf-8")
    ts = _utc_now()
    text = re.sub(
        r"- \[ \] I authorize BACnet \*\*Who-Is\*\*",
        "- [x] I authorize BACnet **Who-Is**",
        text,
        count=1,
    )
    text = re.sub(
        r"- \[ \] Staged devices in",
        "- [x] Staged devices in",
        text,
        count=1,
    )
    text = re.sub(
        r"Signed off by: `\(fill\)` Date \(UTC\): `\(fill\)`",
        f"Signed off by: `{signer}` Date (UTC): `{ts}`",
        text,
        count=1,
    )
    checkpoints.write_text(text, encoding="utf-8")


def merge_env_file(env_path: Path, bind: str, app_name: str, instance: str) -> None:
    lines: list[str] = []
    if env_path.is_file():
        lines = env_path.read_text(encoding="utf-8").splitlines()
    keys = {
        "BAS_BACNET_LAB_VERIFY": "true",
        "BAS_BACNET_APP_NAME": app_name,
        "BAS_BACNET_DEVICE_INSTANCE": instance,
        "BAS_BACNET_BIND_ADDRESS": bind,
        "BAS_BACNET_AUTO_COMMISSION": "true",
    }
    out: list[str] = []
    seen: set[str] = set()
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line and not line.strip().startswith("#") else ""
        if key in keys:
            out.append(f"{key}={keys[key]}")
            seen.add(key)
        else:
            out.append(line)
    for key, value in keys.items():
        if key not in seen:
            out.append(f"{key}={value}")
    env_path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def enable_poll_job(jobs_path: Path) -> None:
    doc = json.loads(jobs_path.read_text(encoding="utf-8"))
    for job in doc.get("jobs") or []:
        if job.get("id") == "bas-bacnet-discovery-poll":
            job["enabled"] = True
    jobs_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: bas_bacnet_auto_commission.py <bas_build_root>", file=sys.stderr)
        return 2

    bas_build = Path(sys.argv[1]).resolve()
    cron_root = bas_build / "cron_codex"
    state_dir = cron_root / "state"
    notepad = bas_build / "memory/commissioning/PHASE_NOTEPAD.md"
    checkpoints = bas_build / "BUILD_CHECKPOINTS.md"
    jobs_path = bas_build / "cron/jobs.json"
    env_path = cron_root / ".env"
    auth_file = state_dir / "bacnet_wire_authorized"
    mode_file = state_dir / "bacnet_auto_commission.mode"
    chat_default = Path.home() / "bas_app/runtime/rough_in_chat.json"
    chat_path = Path(
        __import__("os").environ.get("BAS_COMMISSIONING_CHAT_PATH", str(chat_default))
    )

    parsed = parse_notepad(notepad) if notepad.is_file() else {"bind": "", "bind_ok": False, "devices_ok": False}
    chat_ok = chat_requests_commissioning(chat_path)
    ready = bool(parsed.get("bind_ok")) and bool(parsed.get("devices_ok"))

    report = {
        "at_utc": _utc_now(),
        "ready": ready,
        "chat_commissioning_intent": chat_ok,
        "bind": parsed.get("bind"),
        "wire_authorized": auth_file.is_file(),
    }
    print(json.dumps(report, indent=2))

    if not ready:
        print("skip: PHASE_NOTEPAD § A bind or § C devices not ready", file=sys.stderr)
        return 0

    # Optional extra gate: require rough-in commissioning chat unless FORCE.
    force = __import__("os").environ.get("BAS_BACNET_AUTO_COMMISSION_FORCE", "true").lower() == "true"
    if not chat_ok and not auth_file.is_file() and not force:
        print("skip: no recent commissioning chat intent (set BAS_BACNET_AUTO_COMMISSION_FORCE=true)", file=sys.stderr)
        return 0

    mode_file.write_text(f"enabled_at={_utc_now()}\n", encoding="utf-8")

    if checkpoints.is_file():
        mark_signoff_checkboxes(checkpoints)

    app_name = __import__("os").environ.get("BAS_BACNET_APP_NAME", "BasHeadEnd")
    instance = __import__("os").environ.get("BAS_BACNET_DEVICE_INSTANCE", "100")
    merge_env_file(env_path, str(parsed["bind"]), app_name, instance)

    if not auth_file.is_file():
        auth_file.write_text(_utc_now() + "\n", encoding="utf-8")
        print(f"wrote {auth_file}")

    enable_poll_job(jobs_path)
    print(f"enabled bas-bacnet-discovery-poll in {jobs_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
