#!/usr/bin/env python

"""
Fake AHU BACnet Device for GL36 Trim & Respond Testing
======================================================

This script creates a fake AHU BACnet/IP device using BACpypes3.

It is meant to be paired with Niagara GL36 logic for:
- Duct Static Pressure Trim & Respond  -> DAP-SP
- Supply Air Temperature Trim & Respond -> SAT-SP
- Fan run command/status, OA-T, etc.

Usage:
    python fake_ahu.py --name BensFakeAhu --instance 3456789 [--debug]

You can then discover and bind to these points from a BACnet client / Niagara.
"""

import asyncio
import logging
import random

from bacpypes3.argparse import SimpleArgumentParser
from bacpypes3.app import Application

from bacpypes3.local.analog import (
    AnalogValueObject,
    AnalogInputObject,
    AnalogOutputObject,
)
from bacpypes3.local.binary import BinaryInputObject, BinaryOutputObject
from bacpypes3.local.cmd import Commandable
from bacpypes3.object import MultiStateValueObject

UPDATE_INTERVAL_SECONDS = 5


class CommandableAnalogValueObject(Commandable, AnalogValueObject):
    """Commandable Analog Value Object"""


class CommandableMultiStateValueObject(Commandable, MultiStateValueObject):
    """Commandable Multi-State Value Object"""


class FakeAHUApplication:
    """
    Fake AHU BACnet device.

    Intended to pair with:
      - GL36 Duct Static Trim & Respond (drives DAP-SP)
      - GL36 SAT Trim & Respond (drives SAT-SP)

    Typical Niagara mapping:
      fanRunCmd              -> SF-C (BinaryOutput)
      DischargeAirPressureSp -> DAP-SP (AnalogValue)
      DischargeAirTempSp     -> SAT-SP (AnalogValue)
    """

    def __init__(self, args):
        self.app = Application.from_args(args)

        # AHU-level BACnet objects (no VAV points in this device)
        self.points = {
            # ------------- Analog Inputs (Sensors) -------------
            "DAP-P": AnalogInputObject(
                objectIdentifier=("analogInput", 1),
                objectName="DAP-P",
                presentValue=1.0,
                units="inchesOfWater",
                description="AHU Duct Static Pressure",
            ),
            "SA-T": AnalogInputObject(
                objectIdentifier=("analogInput", 2),
                objectName="SA-T",
                presentValue=55.0,
                units="degreesFahrenheit",
                description="Supply Air Temperature",
            ),
            "MA-T": AnalogInputObject(
                objectIdentifier=("analogInput", 3),
                objectName="MA-T",
                presentValue=70.0,
                units="degreesFahrenheit",
                description="Mixed Air Temperature",
            ),
            "RA-T": AnalogInputObject(
                objectIdentifier=("analogInput", 4),
                objectName="RA-T",
                presentValue=72.0,
                units="degreesFahrenheit",
                description="Return Air Temperature",
            ),
            "SA-FLOW": AnalogInputObject(
                objectIdentifier=("analogInput", 5),
                objectName="SA-FLOW",
                presentValue=10000.0,
                units="cubicFeetPerMinute",
                description="Supply Airflow",
            ),
            "OA-T": AnalogInputObject(
                objectIdentifier=("analogInput", 6),
                objectName="OA-T",
                presentValue=60.0,
                units="degreesFahrenheit",
                description="Outside Air Temperature (Local Sensor)",
            ),
            "ELEC-PWR": AnalogInputObject(
                objectIdentifier=("analogInput", 7),
                objectName="ELEC-PWR",
                presentValue=150.0,
                units="kilowatts",
                description="Building Electrical Power",
            ),

            # ------------- Analog Outputs (Commands) -------------
            # NOTE: AnalogOutputObject from bacpypes3.local.analog is already commandable,
            # so do NOT mix in Commandable again (would cause MRO error).
            "SF-O": AnalogOutputObject(
                objectIdentifier=("analogOutput", 1),
                objectName="SF-O",
                presentValue=50.0,
                units="percent",
                covIncrement=1.0,
                description="Supply Fan Speed Command",
            ),
            "HTG-O": AnalogOutputObject(
                objectIdentifier=("analogOutput", 2),
                objectName="HTG-O",
                presentValue=0.0,
                units="percent",
                covIncrement=1.0,
                description="Heating Valve Command",
            ),
            "CLG-O": AnalogOutputObject(
                objectIdentifier=("analogOutput", 3),
                objectName="CLG-O",
                presentValue=0.0,
                units="percent",
                covIncrement=1.0,
                description="Cooling Valve Command",
            ),
            "DPR-O": AnalogOutputObject(
                objectIdentifier=("analogOutput", 4),
                objectName="DPR-O",
                presentValue=0.0,
                units="percent",
                covIncrement=1.0,
                description="Mixing Dampers Command",
            ),

            # ------------- Analog Values (Setpoints) -------------
            # GL36 Duct Static Trim & Respond -> DischargeAirPressureSp
            "DAP-SP": CommandableAnalogValueObject(
                objectIdentifier=("analogValue", 1),
                objectName="DAP-SP",
                presentValue=1.0,  # in. w.c.
                units="inchesOfWater",
                covIncrement=0.01,
                description="Duct Static Pressure Setpoint (DischargeAirPressureSp)",
            ),

            # GL36 SAT Trim & Respond -> DischargeAirTempSp
            "SAT-SP": CommandableAnalogValueObject(
                objectIdentifier=("analogValue", 2),
                objectName="SAT-SP",
                presentValue=55.0,
                units="degreesFahrenheit",
                covIncrement=0.1,
                description="Supply Air Temperature Setpoint (DischargeAirTempSp)",
            ),

            "OAT-NETWORK": CommandableAnalogValueObject(
                objectIdentifier=("analogValue", 3),
                objectName="OAT-NETWORK",
                presentValue=60.0,
                units="degreesFahrenheit",
                covIncrement=0.1,
                description="Outside Air Temperature (Network / Averaged)",
            ),

            # ------------- Binary Points -------------
            "SF-S": BinaryInputObject(
                objectIdentifier=("binaryInput", 1),
                objectName="SF-S",
                presentValue="active",
                description="Supply Fan Status",
            ),
            "SF-C": BinaryOutputObject(
                objectIdentifier=("binaryOutput", 1),
                objectName="SF-C",
                presentValue="inactive",
                description="Supply Fan Command (fanRunCmd)",
            ),

            # ------------- Multi-State (Occupancy Schedule) -------------
            "Occ-Schedule": CommandableMultiStateValueObject(
                objectIdentifier=("multiStateValue", 1),
                objectName="Occ-Schedule",
                presentValue=1,  # 1 = Occupied
                numberOfStates=4,
                stateText=["Not Set", "Occupied", "UnOccupied", "Standby"],
                description="Occupancy Schedule State",
            ),
        }

        for obj in self.points.values():
            self.app.add_object(obj)

        asyncio.create_task(self.update_values())

    async def update_values(self):
        """
        Simulate changing sensor values.
        Commandable points (SPs, outputs, schedule) are left alone so Niagara / GL36 can drive them.
        """
        while True:
            await asyncio.sleep(UPDATE_INTERVAL_SECONDS)
            print("=" * 50)
            print("Fake AHU – updating sensor values")

            for name, obj in self.points.items():
                # Only wiggle AIs and BI; show others
                if isinstance(obj, AnalogInputObject):
                    if name == "ELEC-PWR":
                        new_value = random.uniform(120.0, 300.0)
                    elif name == "SA-T":
                        new_value = random.uniform(53.0, 60.0)
                    elif name == "DAP-P":
                        new_value = random.uniform(0.3, 1.5)
                    elif name == "OA-T":
                        new_value = random.uniform(30.0, 95.0)
                    else:
                        new_value = random.uniform(40.0, 80.0)

                    obj.presentValue = new_value
                    print(f"AI  {name}: {new_value:.2f}")

                elif isinstance(obj, BinaryInputObject):
                    new_value = random.choice(["active", "inactive"])
                    obj.presentValue = new_value
                    print(f"BI  {name}: {new_value}")

                else:
                    # Just print current commandable/outputs without changing them
                    try:
                        pv = obj.presentValue
                    except AttributeError:
                        pv = "<no presentValue>"
                    print(f"CMD {name}: {pv}")


async def main():
    logging.basicConfig(level=logging.INFO)
    args = SimpleArgumentParser().parse_args()
    logging.info("args: %r", args)

    FakeAHUApplication(args)
    await asyncio.Future()  # run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("BACnet AHU simulation stopped.")
