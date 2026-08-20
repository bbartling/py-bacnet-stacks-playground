"""Redact machine-local paths from A04-v2 JSON artifacts. Does not touch parquet metrics."""
from __future__ import annotations

import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP))

from eplus_gym.path_sanitize import redact_json_file


def main() -> int:
    root = _APP / "docs" / "audits" / "figures" / "a04v2"
    n = 0
    for path in root.rglob("*.json"):
        if "eplus" in path.parts or "stageB" in path.parts:
            continue
        if redact_json_file(path):
            n += 1
            print(path.relative_to(_APP).as_posix())
    print(f"redacted {n} json files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
