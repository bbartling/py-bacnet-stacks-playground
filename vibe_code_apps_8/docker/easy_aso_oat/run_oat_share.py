"""
Outside-air (or any single-source) share loop for BAS Lite.

Uses easy-aso's JsonRpcBacnetClient against diy-bacnet (same JSON-RPC path as the API)
so we do not open a second BACnet/IP UDP socket in the stack.

Configure with environment variables (see docker-compose / .env.example).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import traceback
from typing import Any, List

from easy_aso.bacnet_client.jsonrpc_client import JsonRpcBacnetClient

LOG = logging.getLogger("oat-share")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _targets() -> List[dict[str, Any]]:
    raw = os.environ.get("OAT_TARGET_WRITES", "[]")
    try:
        v = json.loads(raw)
        return v if isinstance(v, list) else []
    except Exception:
        LOG.warning("OAT_TARGET_WRITES is not valid JSON; using []")
        return []


async def main() -> None:
    src_addr = os.environ.get("OAT_SOURCE_DEVICE", "").strip()
    src_obj = os.environ.get("OAT_SOURCE_OBJECT", "").strip()
    if not src_addr or not src_obj:
        LOG.error("Set OAT_SOURCE_DEVICE and OAT_SOURCE_OBJECT (BACnet device + object id, e.g. 192.168.1.5 and analog-input,1).")
        raise SystemExit(2)

    targets = _targets()
    if not targets:
        LOG.warning("OAT_TARGET_WRITES is empty; agent will read but never write.")

    interval = max(30, int(os.environ.get("OAT_INTERVAL_SEC", "300")))
    base = os.environ.get("SUPERVISOR_BACNET_RPC_URL", "http://diy-bacnet:8080").rstrip("/")
    entry = os.environ.get("SUPERVISOR_BACNET_RPC_ENTRYPOINT", "/api").strip()
    if not entry.startswith("/"):
        entry = "/" + entry

    tok = (os.environ.get("BACNET_RPC_API_KEY") or "").strip() or None
    client = JsonRpcBacnetClient(base, entrypoint=entry, bearer_token=tok)
    try:
        while True:
            try:
                val = await client.read(src_addr, src_obj)
                LOG.info("read %s %s -> %s", src_addr, src_obj, val)
                for t in targets:
                    addr = str(t.get("device") or t.get("address") or "").strip()
                    obj = str(t.get("object") or "").strip()
                    pri = int(t.get("priority", 16))
                    if not addr or not obj:
                        continue
                    await client.write(addr, obj, val, priority=pri)
                    LOG.info("write %s %s <- %s (pri %s)", addr, obj, val, pri)
            except Exception:
                LOG.error("cycle failed: %s", traceback.format_exc())
            await asyncio.sleep(interval)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
