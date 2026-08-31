# Phase 2 PICS-like evidence (project lab — not BTL certification)

This document records **tested** BACnet Device and point behavior for the Vibe13 Rust MS/TP mini-device. It is derived from automated acceptance (`mstp-probe --profile gate`) and live service reads — not an official PICS submission.

**Pin:** `jscott3201/rusty-bacnet` @ `af4e88680c51eb4da64dac47f0540a35bf184732`  
**Device:** instance `123001`, MAC `3`, standard frames only, `Max_APDU_Length_Accepted=480`, `Segmentation_Supported=no segmentation`.

## Device object (ReadProperty verified)

| Property | Expected / observed |
|----------|---------------------|
| Object_Identifier | `device,123001` |
| Object_Name | `Rust MS/TP Mini Device` |
| Object_Type | `device` (8) |
| System_Status | operational (0) |
| Vendor_Name | `vibe13-mstp-lab` |
| Vendor_Identifier | 999 (lab placeholder) |
| Model_Name | `mstp-mini-device` |
| Application_Software_Version | crate `0.1.0` |
| Protocol_Version / Protocol_Revision | 1 / 22 |
| Protocol_Services_Supported | bitstring (loopback + hardware acceptance) |
| Protocol_Object_Types_Supported | device + AI/BI/AV/BV |
| Object_List[0] | array count 5 |
| Object_List[1..] | device + AI:1 + BI:1 + AV:2 + BV:2 |
| Max_APDU_Length_Accepted | 480 |
| Segmentation_Supported | no segmentation (3) |
| APDU_Timeout | 6000 ms |
| Number_Of_APDU_Retries | 3 |

## Point services (BACnet services)

| Service | Result |
|---------|--------|
| Who-Is / I-Am | PASS |
| ReadProperty Device/Object_Name | PASS |
| ReadProperty AI:1 / BI:1 Present_Value | PASS |
| ReadPropertyMultiple | PASS |
| WriteProperty AV:2 @ priority 8 + readback | PASS |
| Relinquish AV:2 @ priority 8 (NULL) | PASS |
| WriteProperty BV:2 + relinquish | PASS |
| WriteProperty AI:1 / BI:1 Present_Value | write-access-denied |
| Unknown object AI:99 | unknown-object |
| Invalid Object_List index | invalid-array-index |
| Unknown property array index | property-is-not-an-array |

## Explicit non-claims

- Not Clause 9 conformant
- Not BTL certified
- No extended MS/TP (types 32/33)
- No MS/TP segmentation
- No simultaneous FEC mirror + local server
- Not a BACnet router

Historical captures labeled `19d205d` / `e3b9edb` predate this pin and require revalidation before reuse.
