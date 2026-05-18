#!/usr/bin/env python

# Dev note / example run command:
# (env) ben@rpi3b:~$ python fake_vav.py --name Zone1VAV --instance 3456790

"""
Fake VAV Box BACnet Device for GL36 VAV Request Testing
=======================================================

This script creates a fake SINGLE VAV box as a BACnet/IP device using BACpypes3.

It is meant to be paired with Niagara GL36 logic for:
- VAV Box Zone Request Generator
- Counting vavCoolRequests and vavPressureRequests
- Feeding aggregate requests up to the AHU Trim & Respond blocks

Exposed Points (typical mapping to ProgramObject slots):
--------------------------------------------------------
- ZoneTemp       (AI)  -> zoneTemp
- ZoneCoolingSpt (AV)  -> zoneCoolingSpt
- ZoneDemand     (AV)  -> zoneDemand (0–100%)
- VAVFlow        (AI)  -> vavFlow
- VAVFlowSpt     (AV)  -> vavFlowSpt
- VAVDamperCmd   (AO)  -> vavDamperCmd

Usage:
------
    python fake_vav.py --name Zone1VAV --instance 3456790 [--debug]

You can start multiple VAVs by running this script multiple times with
different --name / --instance (and ports if needed).
"""

import asyncio
import logging
import random

from bacpypes3.argparse import SimpleArgumentParser
from bacpypes3.app import Application
from bacpypes3.local.analog import (
    AnalogInputObject,
    AnalogValueObject,
    AnalogOutputObject,
)
from bacpypes3.local.cmd import Commandable

UPDATE_INTERVAL_SECONDS = 20.0


class CommandableAnalogValueObject(Commandable, AnalogValueObject):
    """Commandable Analog Value Object"""


class FakeVAVApplication:
    """
    Fake single VAV BACnet device.

    Exposes the GL36 VAV box variables as BACnet points:
      - ZoneTemp          (AI)
      - ZoneCoolingSpt    (AV, commandable)
      - ZoneDemand        (AV, commandable / simulated)
      - VAVFlow           (AI)
      - VAVFlowSpt        (AV, commandable)
      - VAVDamperCmd      (AO, commandable, but AnalogOutputObject is already commandable)

    These should map 1:1 to the Niagara ProgramObject slots:
      zoneTemp, zoneCoolingSpt, zoneDemand,
      vavFlow, vavFlowSpt, vavDamperCmd
    """

    def __init__(self, args):
        self.app = Application.from_args(args)

        # Core VAV points for GL36
        self.points = {
            # ------------- Analog Inputs (measured) -------------
            "ZoneTemp": AnalogInputObject(
                objectIdentifier=("analogInput", 1),
                objectName="ZoneTemp",
                presentValue=72.0,
                units="degreesFahrenheit",
                description="Zone Air Temperature",
            ),
            "VAVFlow": AnalogInputObject(
                objectIdentifier=("analogInput", 2),
                objectName="VAVFlow",
                presentValue=400.0,
                units="cubicFeetPerMinute",
                description="Measured VAV Airflow",
            ),

            # ------------- Analog Values (setpoints / loops) -------------
            "ZoneCoolingSpt": CommandableAnalogValueObject(
                objectIdentifier=("analogValue", 1),
                objectName="ZoneCoolingSpt",
                presentValue=72.0,
                units="degreesFahrenheit",
                covIncrement=0.1,
                description="Zone Cooling Setpoint",
            ),
            "ZoneDemand": CommandableAnalogValueObject(
                objectIdentifier=("analogValue", 2),
                objectName="ZoneDemand",
                presentValue=0.0,
                units="percent",
                covIncrement=1.0,
                description="Cooling Loop Output / Zone Demand (0–100%)",
            ),
            "VAVFlowSpt": CommandableAnalogValueObject(
                objectIdentifier=("analogValue", 3),
                objectName="VAVFlowSpt",
                presentValue=800.0,
                units="cubicFeetPerMinute",
                covIncrement=5.0,
                description="VAV Airflow Setpoint",
            ),

            # ------------- Analog Output (damper cmd) -------------
            # NOTE: AnalogOutputObject from bacpypes3.local.analog is already commandable.
            "VAVDamperCmd": AnalogOutputObject(
                objectIdentifier=("analogOutput", 1),
                objectName="VAVDamperCmd",
                presentValue=50.0,
                units="percent",
                covIncrement=1.0,
                description="VAV Damper Command (%)",
            ),
        }

        for obj in self.points.values():
            self.app.add_object(obj)

        asyncio.create_task(self.update_values())

    async def update_values(self):
        """
        Simple fake physics loop:

          - ZoneTemp wiggles around ZoneCoolingSpt with some noise.
          - ZoneDemand ramps up when ZoneTemp > ZoneCoolingSpt + 1°F,
            and ramps down when ZoneTemp < ZoneCoolingSpt - 1°F.
          - VAVFlow ~ VAVFlowSpt * (VAVDamperCmd / 100) with noise.

        Niagara is free to command:
          - ZoneCoolingSpt (e.g., from zone setpoint logic)
          - ZoneDemand (e.g., if you write your own PID loop)
          - VAVFlowSpt & VAVDamperCmd (e.g., from GL36 VAV logic)
        """
        while True:
            await asyncio.sleep(UPDATE_INTERVAL_SECONDS)
            print("=" * 50)
            print("Fake VAV – updating sensor/loop values")

            zt = self.points["ZoneTemp"]
            zsp = self.points["ZoneCoolingSpt"]
            zd = self.points["ZoneDemand"]
            vf = self.points["VAVFlow"]
            vfsp = self.points["VAVFlowSpt"]
            damper = self.points["VAVDamperCmd"]

            # Current values
            zsp_val = float(zsp.presentValue)
            damper_val = max(0.0, min(100.0, float(damper.presentValue)))
            vfsp_val = max(0.0, float(vfsp.presentValue))
            demand_val = float(zd.presentValue)

            # --- ZoneTemp: hover around setpoint with +/- 3°F noise ---
            new_zone_temp = zsp_val + random.uniform(-3.0, 3.0)
            zt.presentValue = new_zone_temp

            # --- ZoneDemand: simple "hot -> up, cold -> down" behavior ---
            if new_zone_temp > zsp_val + 1.0:
                demand_val = min(100.0, demand_val + random.uniform(5.0, 15.0))
            elif new_zone_temp < zsp_val - 1.0:
                demand_val = max(0.0, demand_val - random.uniform(5.0, 15.0))
            else:
                # small drift toward 50% around setpoint
                if demand_val > 50.0:
                    demand_val -= random.uniform(0.0, 5.0)
                else:
                    demand_val += random.uniform(0.0, 5.0)
            zd.presentValue = demand_val

            # --- VAVFlow: proportional to damper * setpoint + some noise ---
            ratio = damper_val / 100.0
            base_flow = vfsp_val * ratio if vfsp_val > 0 else 0.0
            new_flow = max(0.0, base_flow + random.uniform(-50.0, 50.0))
            vf.presentValue = new_flow

            # Print out values for quick terminal debugging
            print(f"ZoneTemp:       {zt.presentValue:.2f} °F")
            print(f"ZoneCoolingSpt: {zsp.presentValue:.2f} °F")
            print(f"ZoneDemand:     {zd.presentValue:.1f} %")
            print(f"VAVFlow:        {vf.presentValue:.1f} cfm")
            print(f"VAVFlowSpt:     {vfsp.presentValue:.1f} cfm")
            print(f"VAVDamperCmd:   {damper.presentValue:.1f} %")


async def main():
    logging.basicConfig(level=logging.INFO)
    args = SimpleArgumentParser().parse_args()
    logging.info("args: %r", args)

    FakeVAVApplication(args)
    await asyncio.Future()  # run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("BACnet VAV simulation stopped.")
