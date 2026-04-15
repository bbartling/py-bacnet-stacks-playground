"""RpcDockedEasyASO: read one OAT (or any) source and fan-out writes — building-agnostic via env JSON."""

from __future__ import annotations

import asyncio
import logging
import os

from easy_aso.runtime.rpc_docked import RpcDockedEasyASO

from agents._bacutil import load_json_env, pv_float

LOG = logging.getLogger("easy-aso.oat-share")


class OatShareAgent(RpcDockedEasyASO):
    async def on_start(self) -> None:
        LOG.info("OatShareAgent started (oat share via JSON-RPC)")

    async def on_step(self) -> None:
        step = float(os.environ.get("EASY_ASO_STEP_SEC", os.environ.get("OAT_INTERVAL_SEC", "300")))
        src_dev = (os.environ.get("OAT_SOURCE_DEVICE") or "").strip()
        src_obj = (os.environ.get("OAT_SOURCE_OBJECT") or "").strip()
        targets = load_json_env("OAT_TARGET_WRITES", [])
        if not src_dev or not src_obj:
            LOG.warning("OAT_SOURCE_DEVICE / OAT_SOURCE_OBJECT not set; idle")
            await asyncio.sleep(max(10.0, step))
            return
        if not isinstance(targets, list) or not targets:
            LOG.warning("OAT_TARGET_WRITES empty; idle")
            await asyncio.sleep(max(10.0, step))
            return

        raw = await self.bacnet_read(src_dev, src_obj)
        pv = pv_float(raw)
        if pv is None:
            LOG.warning("source read failed or non-numeric: %s %s -> %s", src_dev, src_obj, raw)
            await asyncio.sleep(max(10.0, step))
            return

        for t in targets:
            if not isinstance(t, dict):
                continue
            dev = str(t.get("device", "")).strip()
            obj = str(t.get("object", "")).strip()
            if not dev or not obj:
                continue
            pri = t.get("priority", -1)
            try:
                ipri = int(pri) if pri is not None else -1
            except (TypeError, ValueError):
                ipri = -1
            await self.bacnet_write(dev, obj, pv, priority=ipri)
            LOG.info("wrote OAT %.3f -> %s %s", pv, dev, obj)

        await asyncio.sleep(max(5.0, step))

    async def on_stop(self) -> None:
        LOG.info("OatShareAgent stopping")
        await self.close_rpc_dock()
