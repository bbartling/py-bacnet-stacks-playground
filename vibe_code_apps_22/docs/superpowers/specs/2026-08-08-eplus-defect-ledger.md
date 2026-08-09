# E+ defect ledger (2026-08-08)

Machine-readable source: [`2026-08-08-eplus-defect-ledger.json`](2026-08-08-eplus-defect-ledger.json).

Frozen champion: `B_equip_mult_mid` (unchanged parent/baseline) at git `0939584`. Site freeze: `eplus/campaigns/freeze_pre_schedule_plant_20260808T143015Z`.

| ID | Status | One-line |
| --- | --- | --- |
| DEF-SCH-HVAC-OFF | open | SCH_HVAC zeros overnight + weekends; IdealLoads avail/heat/cool all tied |
| DEF-IDEAL-NOLIMIT | open | Heating/cooling NoLimit |
| DEF-WEEKEND-KW-COLLAPSE | open | Winter weekend sim ≈ 12.41 kW vs measured ≈ 64 kW |
| DEF-JAN-ZONE-TEMP-BIAS | open | Jan zone temps cannot track BAS when HVAC forced off |
| DEF-EPW-CALENDAR | open | EPW no holiday/DST; break days as ordinary weekdays |
| DEF-ZONE-AGG-MISSING | open | Extractor omits Library/Gym/Cafe → six-zone contract |
| DEF-STEP0-LAG | open | Real 00:00 vs E+ 00:15; same-row lag fill |
| DEF-TORCH-FAKE-UNROLL | open | HourCNN is feature-axis CNN, not causal `[B,T,F]` |
| DEF-RESID-HOD-UTC | open | HOD residual labeled local narrative / computed UTC |
| DEF-OA-UNSCHEDULED | open | OA design specs lack occupancy schedule |
| DEF-GROUND-TEMP-SILENT | open | No monthly ground-surface temperatures |

DSM status remains **NO-GO** until raw E+ gates and treatment-effect evidence clear.
