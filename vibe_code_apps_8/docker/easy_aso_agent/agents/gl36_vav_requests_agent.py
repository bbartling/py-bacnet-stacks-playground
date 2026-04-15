"""
GL36-style VAV request accounting over JSON-RPC.

Configure zones with BACnet device instance + request objects; counts requests above thresholds
and optionally writes summary analog values (e.g. for an AHU trim-respond consumer).

Env: EASY_ASO_GL36_VAV_CONFIG (JSON object). Example:

{
  "zones": [
    {"device": "3456790", "cooling_request": "analog-value,1", "heating_request": "analog-value,2"}
  ],
  "cooling_threshold": 0.05,
  "heating_threshold": 0.05,
  "summary_device": "3456789",
  "cooling_count_object": "analog-value,20",
  "heating_count_object": "analog-value,21",
  "trim_respond_object": "analog-value,22"
}
"""

from __future__ import annotations

import asyncio
import logging
import os

from easy_aso.runtime.rpc_docked import RpcDockedEasyASO

from agents._bacutil import load_json_env, pv_float

LOG = logging.getLogger("easy-aso.gl36-vav")


def _zone_list(cfg: dict) -> list[dict]:
    z = cfg.get("zones")
    return z if isinstance(z, list) else []


class Gl36VavRequestsAgent(RpcDockedEasyASO):
    async def on_start(self) -> None:
        LOG.info("Gl36VavRequestsAgent started")

    async def on_step(self) -> None:
        step = float(os.environ.get("EASY_ASO_STEP_SEC", "60"))
        cfg = load_json_env("EASY_ASO_GL36_VAV_CONFIG", {})
        if not isinstance(cfg, dict):
            cfg = {}
        zones = _zone_list(cfg)
        c_thr = float(cfg.get("cooling_threshold", 0.05))
        h_thr = float(cfg.get("heating_threshold", 0.05))

        if not zones:
            LOG.warning("EASY_ASO_GL36_VAV_CONFIG has no zones; idle")
            await asyncio.sleep(max(15.0, step))
            return

        cool_n = 0
        heat_n = 0
        trim_sum = 0.0
        trim_w = 0

        for z in zones:
            if not isinstance(z, dict):
                continue
            dev = str(z.get("device", "")).strip()
            if not dev:
                continue
            c_obj = str(z.get("cooling_request", "")).strip()
            h_obj = str(z.get("heating_request", "")).strip()
            w = float(z.get("weight", 1.0)) or 1.0

            if c_obj:
                cv = pv_float(await self.bacnet_read(dev, c_obj))
                if cv is not None and cv > c_thr:
                    cool_n += 1
                    trim_sum += w * cv
                    trim_w += w
            if h_obj:
                hv = pv_float(await self.bacnet_read(dev, h_obj))
                if hv is not None and hv > h_thr:
                    heat_n += 1

        LOG.info(
            "VAV request scan: cooling_zones=%s heating_zones=%s (n_zones=%s)",
            cool_n,
            heat_n,
            len(zones),
        )

        sdev = str(cfg.get("summary_device", "")).strip()
        if sdev:
            c_out = str(cfg.get("cooling_count_object", "")).strip()
            h_out = str(cfg.get("heating_count_object", "")).strip()
            if c_out:
                await self.bacnet_write(sdev, c_out, float(cool_n))
            if h_out:
                await self.bacnet_write(sdev, h_out, float(heat_n))
            trim_obj = str(cfg.get("trim_respond_object", "")).strip()
            if trim_obj and trim_w > 0:
                await self.bacnet_write(sdev, trim_obj, trim_sum / trim_w)

        await asyncio.sleep(max(10.0, step))

    async def on_stop(self) -> None:
        LOG.info("Gl36VavRequestsAgent stopping")
        await self.close_rpc_dock()
