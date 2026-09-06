# Residential heat-pump model

`residential_heat_pump_home.idf` is a self-contained EnergyPlus 26.1 educational model.

## Claims

- `HYPOTHETICAL_GL14_TUNED_DEMO_MODEL` — no measured utility bills; do **not** fabricate NMBE/CV(RMSE)
- `ILLUSTRATIVE_RESIDENTIAL_ASSUMPTIONS` — ~3500 ft² single-zone detached home

## HVAC basis

Carrier **50EZ060** (5-ton R-410A) performance curves copied from:

`C:\EnergyPlusV26-1-0\DataSets\RooftopPackagedHeatPump.idf`

Install DataSets files are not modified.

## Timestep

`Timestep,12;` → 5-minute **zone** timesteps (288/day). EnergyPlus may use smaller internal HVAC timesteps.

Both meters are reported at `Timestep` frequency, which is what
`vibe23.residential.runner.parse_eplus_csv` requires: it accepts **exactly 288 rows** and
raises otherwise. An hourly `eplusout.csv` (24 rows) parsed with the 5-minute `DT_HOURS`
divisor would inflate kW, kWh, and $ by 12×, so the parser refuses rather than resample.
If you change `Timestep` or an `Output:Meter` reporting frequency, the runner will fail
loudly — fix the IDF, not the parser.

## Weather

Canonical EPW (packaged for wheels / Streamlit Cloud):

[`../src/vibe23/assets/USA_CO_Golden-NREL.724666_TMY3.epw`](../src/vibe23/assets/USA_CO_Golden-NREL.724666_TMY3.epw)

This folder mirrors the same filenames for humans browsing the repo. Studio Inputs can upload an alternate EPW for live campaigns; otherwise the packaged Golden file is used.

## Simplifications you must know before reading results

This is a teaching box, not a calibrated house. Every item below materially changes DSM
behaviour:

| Simplification | Where | Consequence |
|---|---|---|
| **No windows** — zero `FenestrationSurface:Detailed` / `Window` objects | envelope | No solar gain, no daylight, no window conduction. Summer afternoon cooling load is understated and driven only by opaque conduction plus internal gains, so precool value is not representative. |
| **Adiabatic floor** — the floor surface uses `Outside Boundary Condition, Adiabatic` | envelope | No ground coupling and no slab heat capacity exchange. Removes a real thermal buffer and a real winter loss path. |
| **Massless insulation** — envelope layers are `Material:NoMass` (e.g. `R13LAYER`, R=2.29 m²·K/W) | envelope | Pure thermal resistance with **no heat capacity**. The envelope cannot store or lag heat, so the "house as battery" effect comes almost entirely from the item below. |
| **Large furniture mass** — `InternalMass, ZONE ONE Furniture, FurnitureConstruction, 650.16 m²` | zone | This single object supplies most of the model's thermal inertia. Setpoint-shift flexibility is therefore highly sensitive to one hand-set area value. |
| **DX compressor cuts out below −5 °C OAT** — `Minimum Outdoor Dry-Bulb Temperature for Compressor Operation = -5.0` | `Coil:Heating:DX:SingleSpeed` | Below −5 °C outdoor, the heat pump stops and heating falls entirely to the backup coil. |
| **10 kW electric supplemental heat, `ALWAYS_ON`** — `Coil:Heating:Electric, ZONE ONE Sup Heater, efficiency 1.0, 10 000 W` | `Coil:Heating:DX:SingleSpeed` | Backup resistance heat is available at every timestep, capped at 21 °C OAT for supplemental operation. |

### Winter results are probably mostly resistance heat

The two bullets above combine badly on the near-design-cold demo day (Jan 3): once outdoor
drybulb drops under −5 °C the compressor is off and the 10 kW COP-1.0 coil carries the
load. The ~245 kWh/day winter figure should be read as **largely resistance heat, not heat
pump operation** — which is also why winter thermostat flexibility looks weak: shedding a
COP-1.0 resistance load saves energy roughly linearly instead of exploiting a COP curve.

**Before interpreting any winter DSM number, add end-use meters and check the split.** The
model currently exports only `Electricity:Facility` and `Electricity:HVAC`, which cannot
distinguish compressor from backup coil. Add, run, and read:

```
Output:Meter,Heating:Electricity,Timestep;
Output:Meter,Cooling:Electricity,Timestep;
Output:Meter,Fans:Electricity,Timestep;
Output:Meter,InteriorLights:Electricity,Timestep;
Output:Meter,InteriorEquipment:Electricity,Timestep;
Output:Variable,*,Heating Coil Electricity Rate,Timestep;
Output:Variable,*,Heating Coil Heating Rate,Timestep;
```

If `Heating:Electricity` tracks the supplemental coil rather than the DX coil for most of
the day, the winter campaign is measuring resistance-heat curtailment and should be
labelled as such.
