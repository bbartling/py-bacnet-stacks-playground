# Track B — Physically meaningful EnergyPlus plant (design only)

**Status:** DESIGN ONLY for PR #76. Do **not** launch a large IdealLoads→HP parameter campaign until trial-specific utility scoring and holdout-isolated ranking are correct (now landed) and this design is reviewed.

**Product label when built:** `RAW_EPLUS_PHYSICAL_HP_PLANT`  
**Current staged model remains:** `RAW_EPLUS_IDEALLOADS_FIXED_COP` (filename `gshp` is naming only).

## Goal

Replace `ZoneHVAC:IdealLoadsAirSystem` + fixed-COP electrical proxy with a plant that can express:

- Part-load heat-pump electricity
- Fan power
- Loop pump power
- Ventilation / DOAS electricity
- Staging and availability
- Overnight baseload that is currently missing

## Recommended topology (6-zone aggregate)

| Element | Intent | Notes |
| --- | --- | --- |
| ZoneHVAC:WaterToAirHeatPump (or packaged WSHP) | One coil object per thermal zone (6 zones) | Aggregates ~67 physical units; document mapping |
| Coil:Cooling/Heating:WaterToAirHeatPump:EquationFit | Performance curves | **Assumed** coefficients until manufacturer data verified |
| Fan:OnOff / Fan:VariableVolume | Supply fan electricity | Map to BAS fan kW when available |
| Pump:VariableSpeed | Condenser/ground loop | Interim fixed EWT boundary if GLHE not ready |
| GroundHeatExchanger:System **or** PlantLoop with scheduled EWT | Ground coupling | Label interim boundary explicitly |
| OutdoorAir:Mixer / DOAS | Ventilation electricity | Weekend/holiday schedules from BAS |
| Coil:Heating:Electric (supplemental) | Backup heat | Only if BAS shows strip/aux use |

## BAS device mapping inputs (required before coefficients are “known”)

- Loop entering/leaving water temperatures
- Pump VFD feedback / status
- Zone thermostat schedules and occupied/unoccupied
- Unit staging counts or enable signals for the 67 terminals (or a justified sample)
- Fan statuses

Until those are curated, every curve coefficient is **ASSUMED** and must carry sensitivity bounds.

## Aggregation policy

A six-zone plant is acceptable initially if mapping all 67 units is unjustified. Preserve zone-level temperature outputs for comfort validation. Document which physical zones roll into `1F_A` … `2F_B`.

## Sensitivity bounds (first campaign after design approval)

- Heating COP curve scale ∈ [0.7, 1.3]
- Fan W/cfm ∈ documented equipment range
- Pump design head ±20%
- Infiltration / OA rates already explored under IdealLoads — freeze or narrow

Use multi-parameter (LHS / sequential) design — not OFAT alone. Never tune on monthly totals only.

## Acceptance linkage

Physical plant candidates must use the same trial-specific utility monthly pairing and chronological-validation ranking as IdealLoads trials. Locked January winter holdout evaluated once after selection. DSM remains **NO-GO** until treatment-effect evidence exists.
