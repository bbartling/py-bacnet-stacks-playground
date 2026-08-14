# Twin dial playbook (short)

**Any building.** Practice narrative (A04 / Jan‑26 ~285 kW) lives in
[`W2A_PLANT_DIAL.md`](W2A_PLANT_DIAL.md) · skill [`../skills/w2a-plant-dial/SKILL.md`](../skills/w2a-plant-dial/SKILL.md).

## Order: envelope → ops

1. **Envelope / loads first** — WWR, glazing U/SHGC, infiltration, lights/equip/people
   multipliers, massing/zone carve. Fix gross monthly bias before plant gymnastics.
2. **Schedules / setpoints** — occupancy, HVAC avail, occupied/unoccupied SP,
   summer-out windows (do not vacation the wrong month).
3. **Plant / coils last** — COP multipliers, coil capacity, setback depth, optimum
   start. Only after envelope+schedule story is stable.

IdealLoads campaigns use `eplus_campaign` knobs; W2A plant uses
`eplus_native/w2a_plant_knobs.py` on **expanded** IDFs. Never mix families into one
champion file.

## Elec-first vs gas-first

Read monthly % error (sim vs bills) by fuel before picking the next dial:

| Signal | Bias | Prefer |
| --- | --- | --- |
| **Elec-first** | Electric \|err\| large while gas is closer (or no gas meter) | Plugs/lights, fans, cooling COP, electric heat / IdealLoads COP proxy, OA/ERV |
| **Gas-first** | Gas \|err\| large while elec is closer | Heating coil capacity/COP, setback, optimum start, infiltration, envelope U — not lighting cuts |
| Both bad, same sign | Sim high or low on both | Envelope / occupancy / weather window before fuel-specific COP |
| Elec high, gas low (or flip) | Cross-fuel | Check fuel mapping, bill_columns, and whether IdealLoads COP proxy is stealing gas story |

Rule of thumb: chase the fuel whose monthly ±% is **farther from GL14** first;
do not “fix” the good fuel to rescue the bad one.

## Gates

- Monthly GL14: \|NMBE\| ≤ 5%, CVRMSE ≤ 15% (per fuel window you claim).
- Design-day peak gate is **extra** (practice dual champion) — not implied by monthly pass.
- `promote=False` until hourly / DSM acceptance policy says otherwise.
- One hypothesis per campaign folder; never overwrite published champions.
