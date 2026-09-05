#!/usr/bin/env python3
"""Shared validators for Vibe13 Pi-lab identifiers (no network)."""
from __future__ import annotations

import re
import sys

# Short allowlist for run/release path segments (reject traversal).
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
# Full git SHA or documented immutable tag form (tag must still match RUN_ID_RE).
GIT_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")

# Official Waveshare RS485 product ↔ chipset (reconciled 2026-09-05).
# C = FTDI FT232 / 0403:6001; B = CH343 / 1a86:55d3.
MODEL_CHIPSET = {
    "waveshare_c": {"vid_pid": "0403:6001", "driver": "ftdi_sio", "usb_hint": "FTDI"},
    "waveshare_b": {"vid_pid": "1a86:55d3", "driver": "cdc_acm", "usb_hint": "1a86"},
}


def validate_run_id(value: str) -> str:
    if not value or not RUN_ID_RE.fullmatch(value):
        raise ValueError(f"invalid run/release id {value!r}")
    if value in (".", "..") or "/" in value or "\\" in value or ".." in value:
        raise ValueError(f"path traversal rejected in id {value!r}")
    return value


def validate_git_sha(value: str) -> str:
    if not GIT_SHA_RE.fullmatch(value):
        raise ValueError(f"release id must be full 40-char git SHA, got {value!r}")
    return value


def expected_model_for_vid_pid(vid_pid: str) -> str | None:
    for model, meta in MODEL_CHIPSET.items():
        if meta["vid_pid"].lower() == vid_pid.lower():
            return model
    return None


def main(argv: list[str]) -> int:
    # Exact argv: [prog, check-run-id|check-git-sha, <id>]
    if len(argv) != 3:
        print("usage: lab_ids.py check-run-id|check-git-sha <id>", file=sys.stderr)
        return 2
    cmd = argv[1]
    try:
        if cmd == "check-run-id":
            print(validate_run_id(argv[2]))
        elif cmd == "check-git-sha":
            print(validate_git_sha(argv[2]))
        else:
            print("usage: lab_ids.py check-run-id|check-git-sha <id>", file=sys.stderr)
            return 2
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
