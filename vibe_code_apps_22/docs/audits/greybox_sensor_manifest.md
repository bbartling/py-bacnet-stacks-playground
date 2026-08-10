# Grey-box sensor manifest (Lakeside)

**Site scanned:** `C:\Users\ben\OneDrive\Desktop\testing\sp_creekside`
**Present:** 11/19

Honesty: missing points are **UNKNOWN / NOT_IN_SITE_EXPORT**. No BACnet object IDs were invented. Identities for PRESENT rows are **parquet/CSV column names** from the real 15-min store (not BACnet objects).

| Point | Status | Identity |
|---|---|---|
| `facility_kw` | PRESENT_IN_EXPORT | facility_kw |
| `zone_temp_1F_A_f` | PRESENT_IN_EXPORT | zone_temp_1F_A_f |
| `zone_temp_1F_B_f` | PRESENT_IN_EXPORT | zone_temp_1F_B_f |
| `zone_temp_1F_C_f` | PRESENT_IN_EXPORT | zone_temp_1F_C_f |
| `zone_temp_1F_D_f` | PRESENT_IN_EXPORT | zone_temp_1F_D_f |
| `zone_temp_2F_A_f` | PRESENT_IN_EXPORT | zone_temp_2F_A_f |
| `zone_temp_2F_B_f` | PRESENT_IN_EXPORT | zone_temp_2F_B_f |
| `htg_setpoint` | NOT_IN_SITE_EXPORT | UNKNOWN — do not invent BACnet object-id |
| `occupancy` | PRESENT_IN_EXPORT | occupied |
| `hp_enable_or_stage` | NOT_IN_SITE_EXPORT | UNKNOWN — do not invent BACnet object-id |
| `fan_status` | NOT_IN_SITE_EXPORT | UNKNOWN — do not invent BACnet object-id |
| `sat_rat` | NOT_IN_SITE_EXPORT | UNKNOWN — do not invent BACnet object-id |
| `loop_ewt` | NOT_IN_SITE_EXPORT | UNKNOWN — do not invent BACnet object-id |
| `loop_lwt` | NOT_IN_SITE_EXPORT | UNKNOWN — do not invent BACnet object-id |
| `pump_speed_or_kw` | NOT_IN_SITE_EXPORT | UNKNOWN — do not invent BACnet object-id |
| `oat_f` | PRESENT_IN_EXPORT | oat_f |
| `rh_pct` | PRESENT_IN_EXPORT | rh_pct |
| `solar_ghi` | PRESENT_IN_EXPORT | ghi |
| `doas_or_oa_signal` | NOT_IN_SITE_EXPORT | UNKNOWN — do not invent BACnet object-id |

See also `reports/ml/greybox_sensor_manifest.csv` (local / gitignored OK).
