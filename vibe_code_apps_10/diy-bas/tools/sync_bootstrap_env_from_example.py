#!/usr/bin/env python3
"""
Reapply bootstrap auth lines from .env.example into .env on the Pi.
"""
from __future__ import annotations

import sys
from pathlib import Path

KEYS = (
    "DIY_BAS_ADMIN_USERNAME",
    "DIY_BAS_ADMIN_PASSWORD",
    "DIY_BAS_MAINT_USERNAME",
    "DIY_BAS_MAINT_PASSWORD",
    "DIY_BAS_BOOTSTRAP_REFRESH_PASSWORDS",
    "DJANGO_DEBUG",
)


def _parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip().lstrip("\ufeff")
        v = v.replace("\r", "").strip()
        if k:
            out[k] = v
    return out


def _main() -> int:
    root = Path(__file__).resolve().parent.parent
    example_path = root / ".env.example"
    env_path = root / ".env"
    if not example_path.is_file():
        print("sync_bootstrap_env: missing .env.example", file=sys.stderr)
        return 1
    example = _parse_env_file(example_path)
    updates = {k: example[k] for k in KEYS if k in example}
    if not updates:
        print("sync_bootstrap_env: no bootstrap keys in .env.example", file=sys.stderr)
        return 1

    if not env_path.is_file():
        env_path.write_text(example_path.read_text(encoding="utf-8"), encoding="utf-8")
        print("sync_bootstrap_env: created .env from .env.example")
        return 0

    lines = env_path.read_text(encoding="utf-8", errors="replace").splitlines()
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
    print("sync_bootstrap_env: merged bootstrap keys from .env.example into .env")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
