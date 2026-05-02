#!/usr/bin/env python3
"""
Merge DIY_BAS_ADMIN_* and DIY_BAS_MAINT_* from JSON on stdin into repo-root .env.

Used on the Pi during deploy (after optional sync from .env.example) so browser login matches
the Integrator / Building Operator values passed from deploy_to_pi.ps1 or deploy_via_ssh.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

KEYS = (
    "DIY_BAS_ADMIN_USERNAME",
    "DIY_BAS_ADMIN_PASSWORD",
    "DIY_BAS_MAINT_USERNAME",
    "DIY_BAS_MAINT_PASSWORD",
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
        print("apply_deploy_credentials: empty stdin", file=sys.stderr)
        return 1
    try:
        j = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"apply_deploy_credentials: invalid JSON: {e}", file=sys.stderr)
        return 1
    if not isinstance(j, dict):
        print("apply_deploy_credentials: JSON root must be an object", file=sys.stderr)
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
        print("apply_deploy_credentials: no credential keys in JSON", file=sys.stderr)
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
    print("apply_deploy_credentials: merged deploy GUI credential keys into .env")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
