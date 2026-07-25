# ECM interactions and double counting

WattLab preserves progressive one-change-at-a-time EnergyPlus accounting and adds catalog-level interaction warnings.

## Principles

1. Scheduling reduces hours available for downstream OA/reset savings.
2. OA shutdown changes heating and cooling loads.
3. SAT reset affects fan, cooling, and reheat simultaneously.
4. Static reset primarily affects fan energy.
5. VAV minimum reduction affects fan, cooling, heating, and ventilation.
6. G36 packages encompass many component measures — do not stack full package + every component as independent savings.
7. Pneumatic-to-DDC packages may include scheduling and compressor removal.
8. `ECM-OCC-STANDBY-DCV` already sums unoccupied OA closure and occupied DCV;
   do not stack its component estimates as independent savings. It is mutually
   incompatible with standalone `ECM-DCV-CO2` (Easy Buttons warns; `esco-top15`
   includes only the composite).

## Implementation

- `wattlab.ecm.interactions.find_incompatibilities`
- `wattlab.ecm.packages.expand_package`
- Easy-button progressive `vs_previous` savings in `wattlab.easy_button`
- Hypothesis Lab proxy crosscheck preserves both EnergyPlus and proxy originals

Reports should show standalone estimates, incremental package savings, and interaction warnings — never force EnergyPlus to match the spreadsheet proxy.

`ECM-OCC-STANDBY-DCV` requires `ECM-SENSOR-CRITICAL-REFRESH`, retains the
ventilation/IAQ review required by `ECM-DCV-CO2`, and is not an authorization to
operate with zero OA during occupied periods.
