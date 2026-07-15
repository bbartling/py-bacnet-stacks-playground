# Sketchbox Knowledge Baseline

This file summarizes public Sketchbox behavior used by the agent framework.

## Confirmed product behavior

- Sketchbox is a simplified commercial-building energy modeling interface powered by DOE-2.2.
- Buildings use rectangular shells with perimeter and core zoning.
- Loads are distributed uniformly within a shell.
- A shell has one program type, HVAC system, and schedule; multiple shells can represent diverse programs, geometry, and HVAC.
- Shell count should be minimized while preserving materially different HVAC, controls, efficiency features, geometry, or use.
- Geometry priorities include gross floor area, floors, floor-to-floor height, exterior surface area/aspect ratio, and façade window-to-wall ratio.
- Project workflow uses Project, Design, Schedules, Baseline, Measures, and Results tabs.
- Baseline parameters should not be changed arbitrarily.
- Proposed design is represented through progressive measures.
- Results include annual/monthly outputs and measure-level savings; public documentation describes EUI, cost, kWh, and therm metrics.
- Hourly kWh and therm results can be downloaded. More detailed files may be available through downloaded model archives for supported accounts/workflows.
- Blue values are responsive defaults; black values are constant defaults. Overriding a responsive default requires explicit provenance.
- The public App 20 README states there is no public Sketchbox API and the existing integration uses Playwright UI automation.

## Agent implications

1. Build shell partitions from physical/modeling differences, not room lists.
2. Model ECMs individually and progressively.
3. Preserve a clean baseline fingerprint.
4. Store every user-entered or overridden value outside the UI.
5. Use approximations for unsupported HVAC only with explicit limitations.
6. Treat UI automation as replaceable infrastructure.
