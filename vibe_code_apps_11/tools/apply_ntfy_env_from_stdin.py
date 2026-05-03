#!/usr/bin/env python3
"""
Merge DIY_BAS_NTFY_* from JSON on stdin into repo-root .env.

Used on the Pi during deploy so push notification settings from the deploy GUI land on the device
without bundling .env in the zip.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

KEYS = (
    "DIY_BAS_NTFY_ALLOWED",
    "DIY_BAS_NTFY_URL",
    "DIY_BAS_NTFY_TOPIC",
    "DIY_BAS_NTFY_USERNAME",
    "DIY_BAS_NTFY_PASSWORD",
    "DIY_BAS_NTFY_TIMEOUT_SEC",
)


def _merge_keys(env_path: Path, updates: dict[str, str]) -> None:
    text = env_path.read_text(encoding="utf-8", errors="replace") if env_path.is_file() else ""
    lines = text.splitlines()
    seen: set[str] = set()
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k, _, _ = stripped.partition("=")
            k = k.strip()
            if k in updates:
                new_lines.append(f"{k}={updates[k]}")
                seen.add(k)
                continue
        new_lines.append(line)
    for k, v in updates.items():
        if k not in seen:
            new_lines.append(f"{k}={v}")
    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        print("apply_ntfy_env: empty stdin", file=sys.stderr)
        return 1
    try:
        j = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"apply_ntfy_env: invalid JSON: {e}", file=sys.stderr)
        return 1
    if not isinstance(j, dict):
        print("apply_ntfy_env: JSON root must be an object", file=sys.stderr)
        return 1
    updates: dict[str, str] = {}
    for k in KEYS:
        if k not in j:
            continue
        val = j[k]
        if val is None:
            continue
        updates[k] = str(val)
    if not updates:
        print("apply_ntfy_env: no ntfy keys in JSON", file=sys.stderr)
        return 1

    root = Path(__file__).resolve().parent.parent
    env_path = root / ".env"
    if not env_path.is_file():
        example = root / ".env.example"
        if example.is_file():
            env_path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            env_path.write_text("", encoding="utf-8")

    _merge_keys(env_path, updates)
    print("apply_ntfy_env: merged ntfy keys into .env")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
