#!/usr/bin/env python3
"""Run ipv4-to-ipv4 router from JSON for N seconds (no interactive console)."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from bacpypes3.app import Application
from bacpypes3.argparse import JSONArgumentParser


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=60)
    args = parser.parse_args()

    # Load JSON into bacpypes settings the same way JSONArgumentParser does.
    bp = JSONArgumentParser()
    bp.parse_args(["--json", str(args.json)])

    from bacpypes3.settings import settings  # noqa: PLC0415

    router_objects = settings.json["router"]
    app = Application.from_json(router_objects)
    print(f"router up for {args.seconds}s (device 998, nets 100/200)", flush=True)
    try:
        await asyncio.sleep(args.seconds)
    finally:
        app.close()
        print("router stopped", flush=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
