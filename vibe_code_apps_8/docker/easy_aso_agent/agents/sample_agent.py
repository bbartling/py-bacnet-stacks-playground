"""Default sample: RpcDockedEasyASO with a periodic on_step (optional demo read)."""

from __future__ import annotations

import asyncio
import logging
import os

from easy_aso.runtime.rpc_docked import RpcDockedEasyASO

LOG = logging.getLogger("easy-aso-agent")


class SampleAgent(RpcDockedEasyASO):
    async def on_start(self) -> None:
        LOG.info("SampleAgent on_start (module=%s)", __name__)

    async def on_step(self) -> None:
        sec = float(os.environ.get("EASY_ASO_STEP_SEC", "30"))
        addr = os.environ.get("EASY_ASO_DEMO_READ_DEVICE", "").strip()
        obj = os.environ.get("EASY_ASO_DEMO_READ_OBJECT", "").strip()
        if addr and obj:
            val = await self.bacnet_read(addr, obj)
            LOG.info("demo read %s %s -> %s", addr, obj, val)
        else:
            LOG.debug("on_step (no EASY_ASO_DEMO_READ_*); sleeping %.1fs", max(5.0, sec))
        await asyncio.sleep(max(5.0, sec))

    async def on_stop(self) -> None:
        LOG.info("SampleAgent on_stop")
        await self.close_rpc_dock()
