import asyncio
import BAC0

"""
Visit https://github.com/JoelBender/BACpypes3/blob/main/bacpypes3/object.py

bacpypes3/object.py
"""

SLEEP_TIME_SECONDS = 30

VAV_DEVICE_IP = "192.168.204.12"
ZONE_TEMP = "analog-input,1"
VAV_FLOW = "analog-input,2"
ZONE_COOL_STP = "analog-value,1"
ZONE_DEMAND = "analog-value,2"
VAV_FLOW_STP = "analog-value,3"
VAV_DPR_CMD = "analog-output,1"

AHU_DEVICE_IP = "192.168.204.13"
AHU_DAP = "analog-input,1"
AHU_SAT = "analog-input,2"
AHU_MAT = "analog-input,3"
AHU_RAT = "analog-input,4"
AHU_SAFLOW = "analog-input,5"
AHU_OAT = "analog-input,6"
AHU_POWER_MTR = "analog-input,7"
AHU_SF_O = "analog-output,1"
AHU_HTG_VLV = "analog-output,2"
AHU_CLG_VLV = "analog-output,3"
AHU_OA_DPR = "analog-output,4"
AHU_DAP_SP = "analog-value,1"
AHU_SAT_SP = "analog-value,2"
OAT_NETWORKED = "analog-value,3"
AHU_SF_S = "binary-input,1"
AHU_SF_C = "binary-output,1"
AHU_OCC_SCHEDULE = "multi-state-value,1" 


async def main():
    async with BAC0.start(ping=False) as bacnet:
        await asyncio.sleep(1)

        while True:

            vav_rpm_request = {
                "address": VAV_DEVICE_IP,
                "objects": {
                    ZONE_TEMP: ["present-value"],
                    VAV_FLOW: ["present-value"],
                    ZONE_COOL_STP: ["present-value"],
                    ZONE_DEMAND: ["present-value"],
                    VAV_FLOW_STP: ["present-value"],
                    VAV_DPR_CMD: ["present-value"],
                },
            }

            result_vav = await bacnet.readMultiple("", request_dict=vav_rpm_request)

            print("\n VAV RPM Results:")
            for obj, props in result_vav.items():
                value = props[0][1] if props else None
                print(f"{obj} -> {value}")

            ahu_rpm_request = {
                "address": AHU_DEVICE_IP,
                "objects": {
                    AHU_DAP: ["present-value"],
                    AHU_SAT: ["present-value"],
                    AHU_MAT: ["present-value"],
                    AHU_RAT: ["present-value"],
                    AHU_SAFLOW: ["present-value"],
                    AHU_OAT: ["present-value"],
                    AHU_POWER_MTR: ["present-value"],
                    AHU_SF_O: ["present-value"],
                    AHU_HTG_VLV: ["present-value"],
                    AHU_CLG_VLV: ["present-value"],
                    AHU_OA_DPR: ["present-value"],
                    AHU_DAP_SP: ["present-value"],
                    AHU_SAT_SP: ["present-value"],
                    OAT_NETWORKED: ["present-value"],
                    AHU_SF_S: ["present-value"],
                    AHU_SF_C: ["present-value"],
                    AHU_OCC_SCHEDULE: ["present-value"], 
                },
            }


            result_ahu = await bacnet.readMultiple("", request_dict=ahu_rpm_request)

            print("\n AHU RPM Results:")
            for obj, props in result_ahu.items():
                value = props[0][1] if props else None
                print(f"{obj} -> {value}")


            print("\n SLEEPING NOW ... ")

            await asyncio.sleep(SLEEP_TIME_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
