# ECM library (OpenFDD WattLab)

Notes for ECM classes mapped to IDF patches / MeasureBriefs. Prefer skill docs under `.agents/skills/` for procedures.

## Measure sets

See [`measure_sets.json`](measure_sets.json) / [`measure_sets.py`](measure_sets.py):

| Set | Contents |
|---|---|
| **Good** | `ECM-AHU-SCHED-ALIGN` |
| **Better** | + `ECM-CHILLER-LOCKOUT` |
| **Best** | + `ECM-SAT-RESET` + `ECM-GL36-AIRSIDE` |

Expand with `expand_measure_set("best")` or `python easy_button.py --measure-set best`.
