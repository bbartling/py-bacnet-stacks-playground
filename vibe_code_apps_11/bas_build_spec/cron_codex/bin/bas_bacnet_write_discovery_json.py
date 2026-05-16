#!/usr/bin/env python3
"""Write bacnet_discovery_latest.json from point_discovery.py stdout."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def parse_devices(raw: str) -> list[dict]:
    devices: list[dict] = []
    for line in raw.splitlines():
        m = re.search(r"Device Instance:\s*(\d+)\s*\|\s*Address:\s*(\S+)", line)
        if m:
            devices.append({"instance": int(m.group(1)), "address": m.group(2)})
    return devices


def main() -> int:
    if len(argv := sys.argv) < 5:
        print(
            "usage: bas_bacnet_write_discovery_json.py <out.json> <utc_ts> <bind> <ok:0|1> <stdout_file>",
            file=sys.stderr,
        )
        return 2
    out_path = Path(argv[1])
    ts, bind, ok_flag, raw_path = argv[2], argv[3], argv[4], argv[5]
    raw = Path(raw_path).read_text(encoding="utf-8", errors="replace")
    ok = ok_flag == "1"
    payload: dict = {
        "polled_at_utc": ts,
        "bind": bind,
        "ok": ok,
        "iam_count": len(parse_devices(raw)) if ok else 0,
        "devices": parse_devices(raw) if ok else [],
    }
    if ok:
        payload["raw_tail"] = raw[-3000:]
    else:
        payload["error_tail"] = raw[-4000:]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"iam_count": payload["iam_count"], "out": str(out_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
