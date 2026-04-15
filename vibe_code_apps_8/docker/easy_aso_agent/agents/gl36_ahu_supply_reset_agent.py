"""
Generic supply-air temperature (SAT) reset for an AHU — GL36-inspired supervisory loop.

Uses zone air temperatures vs a cooling setpoint band to nudge the SAT setpoint between
min/max limits (recommendation-style defaults are safe for lab: tune gains on site).

Env: EASY_ASO_GL36_AHU_CONFIG (JSON). Example:

{
  "ahu_device": "3456789",
  "supply_air_setpoint": "analog-value,5",
  "supply_air_temp": "analog-input,1",
  "zones": [{"device": "3456790", "zone_temp": "analog-value,3"}],
  "cooling_setpoint_f": 72.0,
  "band_f": 1.5,
  "min_sat_f": 52.0,
  "max_sat_f": 60.0,
  "nominal_sat_f": 55.0,
  "reset_gain": -2.0
}

When max(zone_temp) exceeds cooling_setpoint_f + band_f, SAT setpoint moves toward min_sat_f
(more cooling at the coil). When all zones are colder than setpoint - band_f, SAT drifts up
toward max_sat_f. Values are clamped each step.
"""

from __future__ import annotations

import asyncio
import logging
import os

from easy_aso.runtime.rpc_docked import RpcDockedEasyASO

from agents._bacutil import load_json_env, pv_float

LOG = logging.getLogger("easy-aso.gl36-ahu")


class Gl36AhuSupplyResetAgent(RpcDockedEasyASO):
    def __init__(self, args=None):
        super().__init__(args=args)
        self._sat_sp: float | None = None

    async def on_start(self) -> None:
        LOG.info("Gl36AhuSupplyResetAgent started")

    async def on_step(self) -> None:
        step = float(os.environ.get("EASY_ASO_STEP_SEC", "120"))
        cfg = load_json_env("EASY_ASO_GL36_AHU_CONFIG", {})
        if not isinstance(cfg, dict):
            cfg = {}

        ahu = str(cfg.get("ahu_device", "")).strip()
        sp_obj = str(cfg.get("supply_air_setpoint", "")).strip()
        sat_obj = str(cfg.get("supply_air_temp", "")).strip()
        zones = cfg.get("zones") if isinstance(cfg.get("zones"), list) else []

        if not ahu or not sp_obj:
            LOG.warning("ahu_device / supply_air_setpoint missing in EASY_ASO_GL36_AHU_CONFIG; idle")
            await asyncio.sleep(max(20.0, step))
            return

        if self._sat_sp is None:
            cur = pv_float(await self.bacnet_read(ahu, sp_obj))
            self._sat_sp = cur if cur is not None else float(cfg.get("nominal_sat_f", 55.0))

        sp_cool = float(cfg.get("cooling_setpoint_f", 72.0))
        band = float(cfg.get("band_f", 1.5))
        lo = float(cfg.get("min_sat_f", 52.0))
        hi = float(cfg.get("max_sat_f", 60.0))
        nominal = float(cfg.get("nominal_sat_f", 55.0))
        gain = float(cfg.get("reset_gain", -2.0))

        temps: list[float] = []
        for z in zones:
            if not isinstance(z, dict):
                continue
            dev = str(z.get("device", "")).strip()
            zt = str(z.get("zone_temp", "")).strip()
            if dev and zt:
                t = pv_float(await self.bacnet_read(dev, zt))
                if t is not None:
                    temps.append(t)

        if not temps:
            LOG.debug("no zone temps; holding SAT setpoint")
            await asyncio.sleep(max(15.0, step))
            return

        t_max = max(temps)
        t_min = min(temps)
        err_hi = t_max - (sp_cool + band)
        err_lo = (sp_cool - band) - t_min

        delta = 0.0
        if err_hi > 0:
            delta = gain * err_hi
        elif err_lo > 0:
            delta = -gain * err_lo * 0.5

        target = nominal + delta
        if self._sat_sp is not None:
            # smooth toward target
            self._sat_sp = self._sat_sp + 0.35 * (target - self._sat_sp)
        self._sat_sp = max(lo, min(hi, float(self._sat_sp)))

        await self.bacnet_write(ahu, sp_obj, float(self._sat_sp))

        sat_pv = pv_float(await self.bacnet_read(ahu, sat_obj)) if sat_obj else None
        LOG.info(
            "SAT reset: zones=%s t_max=%.2f t_min=%.2f sp=%.2f sat_sp->%.2f sat_pv=%s",
            len(temps),
            t_max,
            t_min,
            sp_cool,
            float(self._sat_sp),
            sat_pv,
        )

        await asyncio.sleep(max(15.0, step))

    async def on_stop(self) -> None:
        LOG.info("Gl36AhuSupplyResetAgent stopping")
        await self.close_rpc_dock()
