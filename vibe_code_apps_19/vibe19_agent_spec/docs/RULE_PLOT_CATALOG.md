# Rule plot catalog (all 50)

**Audience:** agents / engineers reviewing **Plots** validation cards and FDD DOCX.

One section per cookbook rule, grouped by **mechanical family** (same order as sidebar / Results).
Each chart plots **required (+ optional) roles** present on the mapped frame, plus a **confirmed-fault swim lane**.

| Source | Path |
| --- | --- |
| Catalog | `app/rules/cookbook_catalog.py` |
| Haystack export map | `app/column_map_json.py` → `COOKBOOK_TO_HAYSTACK_POINT` |
| Gates | `app/rules/operational_gate.py` → `RULE_GATES` |
| Chart API | `app/charts.py` → `rule_result_chart` |
| UX contract | [`PLOTS_DOCX_VALIDATION.md`](PLOTS_DOCX_VALIDATION.md) · full 50-rule chart catalog: [`RULE_PLOT_CATALOG.md`](RULE_PLOT_CATALOG.md) |

| Machine inventory | `configs/rule_inventory.yaml` (regenerate: `scripts/generate_rule_configs.py`) |

**Haystack note:** Preferred tags come from `COOKBOOK_TO_HAYSTACK_POINT`. Roles not in that dict
use the extended names in Appendix B (hyphenated Project Haystack–style).

**Sliders:** sidebar **Rule tuning** by category; values live in `session_state.params[rule_id]`.
Confirm delay is usually `confirm_min` (minutes) even when catalog `confirm_seconds` differs.

---

## Index by family

| Family | Count | Rule ids |
| --- | ---: | --- |
| 1 · Sensor validation | 4 | `SV-RANGE`, `SV-FLATLINE`, `SV-SPIKE`, `SV-STALE` |
| 2 · Control loops | 1 | `PID-HUNT-1` |
| 3 · AHU / air handling | 29 | `FC1`, `FC2`, `FC3`, `FC4`, `FC5`, `FC6`, `FC7`, `FC8`, `FC9`, `FC10`, `FC11`, `FC12`, `FC13`, `FC14`, `FC15`, `AHU-SATDEV`, `AHU-DUCTHI`, `AHU-SIMUL`, `OAT-METEO`, `ECON-1`, `ECON-2`, `ECON-3`, `ECON-4`, `ECON-5`, `SCHED-1`, `CMD-1`, `OA-1`, `DMP-1`, `VLV-1` |
| 4 · VAV / terminal | 6 | `VAV-1`, `VAV-3`, `VAV-4`, `VAV-5`, `VAV-REHEAT`, `VAV-7` |
| 5 · Central plant | 5 | `CHW-1`, `CHW-2`, `CHW-3`, `CHW-4`, `CW-OPT-1` |
| 6 · Heat pump | 1 | `HP-1` |
| 7 · Weather / OAT | 1 | `WX-1` |
| 8 · Trim & respond | 3 | `TRIM-1`, `TRIM-3`, `TRIM-4` |

---

## 1 · Sensor validation

### `SV-RANGE` — Sensor out of hard range

**Equation:** Any modeled sensor reads outside its physical hard range (e.g. OAT −60–130°F, SAT 30–150°F, CHWS 30–80°F).

| Field | Value |
| --- | --- |
| Family | `sensor` |
| Equipment kinds | `ahu`, `vav`, `chiller`, `boiler`, `weather`, `zone`, `heatpump` |
| Operational gate | `always` |
| Default confirm | 300s |
| Sweep | `sensor_sweep` |

#### Points → Haystack tags (this chart)

Sweep rule: plots **sensors / control outputs present** on the equipment (see sweep role lists in `cookbook_catalog.py`). No fixed required-role list.

#### Plot series

- Present sweep sensors (temps / statuses on mapped frame)
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Plots sensor-fault summary stats when FAULT; Export sensor fault CSV.

### `SV-FLATLINE` — Sensor flatline (stuck)

**Equation:** Sensor value unchanged (Δ ≤ tolerance) across the flatline window — stuck / frozen sensor.

| Field | Value |
| --- | --- |
| Family | `sensor` |
| Equipment kinds | `ahu`, `vav`, `chiller`, `boiler`, `weather`, `zone`, `heatpump` |
| Operational gate | `conditional` |
| Default confirm | 300s |
| Sweep | `sensor_sweep` |

#### Points → Haystack tags (this chart)

Sweep rule: plots **sensors / control outputs present** on the equipment (see sweep role lists in `cookbook_catalog.py`). No fixed required-role list.

#### Plot series

- Present sweep sensors (temps / statuses on mapped frame)
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `flatline_tol` | Flatline tolerance | °F | 0.1 | 0.02 | 1 | 0.02 |
| `flatline_hours` | Flatline window | h | 1 | 0.5 | 8 | 0.5 |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Plots sensor-fault summary stats when FAULT.

### `SV-SPIKE` — Sensor rate-of-change spike

**Equation:** Sample-to-sample jump exceeds the physical spike limit for the sensor type.

| Field | Value |
| --- | --- |
| Family | `sensor` |
| Equipment kinds | `ahu`, `vav`, `chiller`, `boiler`, `weather`, `zone`, `heatpump` |
| Operational gate | `always` |
| Default confirm | 300s |
| Sweep | `sensor_sweep` |

#### Points → Haystack tags (this chart)

Sweep rule: plots **sensors / control outputs present** on the equipment (see sweep role lists in `cookbook_catalog.py`). No fixed required-role list.

#### Plot series

- Present sweep sensors (temps / statuses on mapped frame)
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `spike_scale` | Spike limit scale | ├ù | 1 | 0.25 | 3 | 0.25 |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Plots sensor-fault summary stats when FAULT.

### `SV-STALE` — Stale data (no fresh samples)

**Equation:** All modeled sensors unchanged over the stale window — data feed likely dropped.

| Field | Value |
| --- | --- |
| Family | `sensor` |
| Equipment kinds | `ahu`, `vav`, `chiller`, `boiler`, `weather`, `zone`, `heatpump` |
| Operational gate | `always` |
| Default confirm | 300s |
| Sweep | `sensor_sweep` |

#### Points → Haystack tags (this chart)

Sweep rule: plots **sensors / control outputs present** on the equipment (see sweep role lists in `cookbook_catalog.py`). No fixed required-role list.

#### Plot series

- Present sweep sensors (temps / statuses on mapped frame)
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `stale_hours` | Stale window | h | 2 | 0.5 | 12 | 0.5 |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Plots sensor-fault summary stats when FAULT.


---

## 2 · Control loops

### `PID-HUNT-1` — Suspected control-output hunting

**Equation:** Rolling 1h total variation of any 0–100% control output (dampers, valves, fan speeds, heat/cool cmds) with span ≥20%, TV ≥500 %·pts, ≥2.5 equivalent cycles, ≥4 reversals — suspected loop hunting (not proof of bad PID alone).

| Field | Value |
| --- | --- |
| Family | `control` |
| Equipment kinds | `ahu`, `vav`, `chiller`, `boiler`, `heatpump` |
| Operational gate | `control_loop` (startup 300s) |
| Default confirm | 0s |
| Sweep | `control_output_sweep` |

#### Points → Haystack tags (this chart)

Sweep rule: plots **sensors / control outputs present** on the equipment (see sweep role lists in `cookbook_catalog.py`). No fixed required-role list.

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `loop_enabled` | `loop-enabled` | optional |

#### Plot series

- Present 0–100% control outputs (dampers / valves / fan cmds)
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `change_deadband_pct` | Ignore changes below | % out | 1 | 0 | 10 | 0.5 |
| `minimum_span_pct` | Minimum observed span | % out | 20 | 5 | 100 | 5 |
| `total_variation_fault_pct` | Total travel threshold | %/h | 500 | 50 | 2000 | 50 |
| `minimum_equivalent_cycles` | Min equivalent cycles | cyc/h | 2.5 | 0.5 | 20 | 0.5 |
| `minimum_reversals` | Min direction reversals | count | 4 | 1 | 40 | 1 |
| `minimum_coverage_pct` | Minimum data coverage | % | 80 | 25 | 100 | 5 |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Fault hours / % on Results + FDD DOCX card; RCx overlays only if roles match a preset.


---

## 3 · AHU / air handling

### `FC1` — Duct static below SP at full fan (GL36 A)

**Equation:** Fan ≥ 87% AND duct static < static SP − 0.12 in.w.c.

| Field | Value |
| --- | --- |
| Family | `ahu` |
| Equipment kinds | `ahu` |
| Operational gate | `fan_running` (startup 300s) |
| Default confirm | 300s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `duct_static` | `duct-static-pressure` | required |
| `duct_static_sp` | `duct-static-pressure-sp` | required |
| `fan_cmd` | `fan-cmd` | required |

#### Plot series

- `duct_static` → `duct-static-pressure`
- `duct_static_sp` → `duct-static-pressure-sp`
- `fan_cmd` → `fan-cmd`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `duct_static_err` | Duct static error | in. w.c. | 0.12 | 0.02 | 0.5 | 0.01 |
| `fan_hi` | Fan high threshold | frac | 0.87 | 0.5 | 1 | 0.01 |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Fault hours / % on Results + FDD DOCX card; RCx overlays only if roles match a preset.

### `FC2` — MAT below OAT/RAT envelope (GL36 B)

**Equation:** Fan on AND MAT − 1.15°F < min(RAT, OAT) − 1.15°F.

| Field | Value |
| --- | --- |
| Family | `ahu` |
| Equipment kinds | `ahu` |
| Operational gate | `fan_running` (startup 600s) |
| Default confirm | 600s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `mat` | `mixed-air-temp` | required |
| `oa_t` | `outside-air-temp` | required |
| `rat` | `return-air-temp` | required |
| `fan_cmd` | `fan-cmd` | required |

#### Plot series

- `mat` → `mixed-air-temp`
- `oa_t` → `outside-air-temp`
- `rat` → `return-air-temp`
- `fan_cmd` → `fan-cmd`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `mix_tol` | Mixing tolerance | °F | 1.15 | 0.25 | 3 | 0.05 |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Fault hours / % on Results + FDD DOCX card; RCx overlays only if roles match a preset.

### `FC3` — MAT above OAT/RAT envelope (GL36 C)

**Equation:** Fan on AND MAT − 1.15°F > max(RAT, OAT) + 1.15°F.

| Field | Value |
| --- | --- |
| Family | `ahu` |
| Equipment kinds | `ahu` |
| Operational gate | `fan_running` (startup 600s) |
| Default confirm | 600s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `mat` | `mixed-air-temp` | required |
| `oa_t` | `outside-air-temp` | required |
| `rat` | `return-air-temp` | required |
| `fan_cmd` | `fan-cmd` | required |

#### Plot series

- `mat` → `mixed-air-temp`
- `oa_t` → `outside-air-temp`
- `rat` → `return-air-temp`
- `fan_cmd` → `fan-cmd`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `mix_tol` | Mixing tolerance | °F | 1.15 | 0.25 | 3 | 0.05 |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Fault hours / % on Results + FDD DOCX card; RCx overlays only if roles match a preset.

### `FC4` — PID hunting (operating-state oscillation)

**Equation:** More than 5 operating-mode entry transitions in any hour (heating/econ/mech modes).

| Field | Value |
| --- | --- |
| Family | `ahu` |
| Equipment kinds | `ahu` |
| Operational gate | `control_loop` (startup 300s) |
| Default confirm | 3600s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `oa_damper_pct` | `outside-air-damper` | required |
| `clg_valve_pct` | `cooling-valve` | required |
| `fan_cmd` | `fan-cmd` | required |

#### Plot series

- `oa_damper_pct` → `outside-air-damper`
- `clg_valve_pct` → `cooling-valve`
- `fan_cmd` → `fan-cmd`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `delta_os_max` | Max mode changes/hr | count | 5 | 2 | 20 | 1 |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Fault hours / % on Results + FDD DOCX card; RCx overlays only if roles match a preset.

### `FC5` — SAT cold when heating commanded (GL36 D)

**Equation:** Fan on AND heating > 1% AND SAT + 1.15°F ≤ MAT − 1.15°F + 0.55°F.

| Field | Value |
| --- | --- |
| Family | `ahu` |
| Equipment kinds | `ahu` |
| Operational gate | `fan_running` (startup 600s) |
| Default confirm | 600s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `sat` | `discharge-air-temp` | required |
| `mat` | `mixed-air-temp` | required |
| `fan_cmd` | `fan-cmd` | required |
| `htg_valve_pct` | `heating-valve` | required |

#### Plot series

- `sat` → `discharge-air-temp`
- `mat` → `mixed-air-temp`
- `fan_cmd` → `fan-cmd`
- `htg_valve_pct` → `heating-valve`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `mix_tol` | Mixing tolerance | °F | 1.15 | 0.25 | 3 | 0.05 |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Fault hours / % on Results + FDD DOCX card; RCx overlays only if roles match a preset.

### `FC6` — Estimated OA fraction mismatch

**Equation:** |RAT−OAT| ≥ 5°F AND |estimated OA% − design min OA%| > 15% in heating/mech-only modes.

| Field | Value |
| --- | --- |
| Family | `ahu` |
| Equipment kinds | `ahu` |
| Operational gate | `fan_running` (startup 600s) |
| Default confirm | 600s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `mat` | `mixed-air-temp` | required |
| `oa_t` | `outside-air-temp` | required |
| `rat` | `return-air-temp` | required |
| `vav_total_flow` | `vav-total-airflow` | required |

#### Plot series

- `mat` → `mixed-air-temp`
- `oa_t` → `outside-air-temp`
- `rat` → `return-air-temp`
- `vav_total_flow` → `vav-total-airflow`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `airflow_err` | OA fraction error | frac | 0.15 | 0.05 | 0.5 | 0.01 |
| `min_cfm_design` | Design min OA CFM | cfm | 5000 | 500 | 20000 | 500 |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Needs AHU `vav_total_flow` — empty plots often data gaps.

### `FC7` — SAT low with full heating (GL36 E)

**Equation:** Fan on AND heating > 90% AND SAT < SAT SP − 1.0°F.

| Field | Value |
| --- | --- |
| Family | `ahu` |
| Equipment kinds | `ahu` |
| Operational gate | `fan_running` (startup 600s) |
| Default confirm | 600s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `sat` | `discharge-air-temp` | required |
| `sat_sp` | `discharge-air-temp-sp` | required |
| `fan_cmd` | `fan-cmd` | required |
| `htg_valve_pct` | `heating-valve` | required |

#### Plot series

- `sat` → `discharge-air-temp`
- `sat_sp` → `discharge-air-temp-sp`
- `fan_cmd` → `fan-cmd`
- `htg_valve_pct` → `heating-valve`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `sat_err` | SAT error | °F | 1 | 0.25 | 5 | 0.25 |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Fault hours / % on Results + FDD DOCX card; RCx overlays only if roles match a preset.

### `FC8` — SAT/MAT mismatch in economizer (GL36 F)

**Equation:** Economizer open, CHW < 10%, |SAT − 0.55°F − MAT| > √(1.15²+1.15²).

| Field | Value |
| --- | --- |
| Family | `ahu` |
| Equipment kinds | `ahu` |
| Operational gate | `fan_running` (startup 600s) |
| Default confirm | 600s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `sat` | `discharge-air-temp` | required |
| `mat` | `mixed-air-temp` | required |
| `oa_damper_pct` | `outside-air-damper` | required |
| `clg_valve_pct` | `cooling-valve` | required |

#### Plot series

- `sat` → `discharge-air-temp`
- `mat` → `mixed-air-temp`
- `oa_damper_pct` → `outside-air-damper`
- `clg_valve_pct` → `cooling-valve`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Fault hours / % on Results + FDD DOCX card; RCx overlays only if roles match a preset.

### `FC9` — OAT too warm for free cooling (GL36 G)

**Equation:** Economizer open, CHW < 10%, OAT − 1.15°F > SAT SP − 0.55°F + 1.15°F.

| Field | Value |
| --- | --- |
| Family | `ahu` |
| Equipment kinds | `ahu` |
| Operational gate | `fan_running` (startup 600s) |
| Default confirm | 600s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `oa_t` | `outside-air-temp` | required |
| `sat_sp` | `discharge-air-temp-sp` | required |
| `oa_damper_pct` | `outside-air-damper` | required |
| `clg_valve_pct` | `cooling-valve` | required |

#### Plot series

- `oa_t` → `outside-air-temp`
- `sat_sp` → `discharge-air-temp-sp`
- `oa_damper_pct` → `outside-air-damper`
- `clg_valve_pct` → `cooling-valve`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Fault hours / % on Results + FDD DOCX card; RCx overlays only if roles match a preset.

### `FC10` — OAT/MAT mismatch + mech cooling (GL36 H)

**Equation:** CHW > 1%, economizer > 90%, |MAT − OAT| > √(1.15²+1.15²).

| Field | Value |
| --- | --- |
| Family | `ahu` |
| Equipment kinds | `ahu` |
| Operational gate | `fan_running` (startup 600s) |
| Default confirm | 600s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `mat` | `mixed-air-temp` | required |
| `oa_t` | `outside-air-temp` | required |
| `oa_damper_pct` | `outside-air-damper` | required |
| `clg_valve_pct` | `cooling-valve` | required |

#### Plot series

- `mat` → `mixed-air-temp`
- `oa_t` → `outside-air-temp`
- `oa_damper_pct` → `outside-air-damper`
- `clg_valve_pct` → `cooling-valve`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Fault hours / % on Results + FDD DOCX card; RCx overlays only if roles match a preset.

### `FC11` — OAT/MAT mismatch economizer-only (GL36 I)

**Equation:** CHW > 1%, economizer > 90%, OAT + 1.15°F < SAT SP − 0.55°F − 1.15°F.

| Field | Value |
| --- | --- |
| Family | `ahu` |
| Equipment kinds | `ahu` |
| Operational gate | `fan_running` (startup 600s) |
| Default confirm | 600s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `oa_t` | `outside-air-temp` | required |
| `sat_sp` | `discharge-air-temp-sp` | required |
| `oa_damper_pct` | `outside-air-damper` | required |
| `clg_valve_pct` | `cooling-valve` | required |

#### Plot series

- `oa_t` → `outside-air-temp`
- `sat_sp` → `discharge-air-temp-sp`
- `oa_damper_pct` → `outside-air-damper`
- `clg_valve_pct` → `cooling-valve`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Fault hours / % on Results + FDD DOCX card; RCx overlays only if roles match a preset.

### `FC12` — SAT above blend in cooling (GL36 J)

**Equation:** CHW > 1%, SAT − 1.15°F − 0.55°F > MAT + 1.15°F at min or full economizer.

| Field | Value |
| --- | --- |
| Family | `ahu` |
| Equipment kinds | `ahu` |
| Operational gate | `fan_running` (startup 600s) |
| Default confirm | 600s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `sat` | `discharge-air-temp` | required |
| `mat` | `mixed-air-temp` | required |
| `oa_damper_pct` | `outside-air-damper` | required |
| `clg_valve_pct` | `cooling-valve` | required |

#### Plot series

- `sat` → `discharge-air-temp`
- `mat` → `mixed-air-temp`
- `oa_damper_pct` → `outside-air-damper`
- `clg_valve_pct` → `cooling-valve`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Fault hours / % on Results + FDD DOCX card; RCx overlays only if roles match a preset.

### `FC13` — SAT above SP at full cooling (GL36 K)

**Equation:** CHW > 1%, SAT > SAT SP + 1.0°F at min or full economizer.

| Field | Value |
| --- | --- |
| Family | `ahu` |
| Equipment kinds | `ahu` |
| Operational gate | `fan_running` (startup 600s) |
| Default confirm | 600s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `sat` | `discharge-air-temp` | required |
| `sat_sp` | `discharge-air-temp-sp` | required |
| `oa_damper_pct` | `outside-air-damper` | required |
| `clg_valve_pct` | `cooling-valve` | required |

#### Plot series

- `sat` → `discharge-air-temp`
- `sat_sp` → `discharge-air-temp-sp`
- `oa_damper_pct` → `outside-air-damper`
- `clg_valve_pct` → `cooling-valve`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `sat_err` | SAT error | °F | 1 | 0.25 | 5 | 0.25 |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Fault hours / % on Results + FDD DOCX card; RCx overlays only if roles match a preset.

### `FC14` — CHW coil ΔT when inactive (GL36 L)

**Equation:** Cooling coil ΔT ≥ √(1.15²+1.15²)+0.55°F while coil should be inactive.

| Field | Value |
| --- | --- |
| Family | `ahu` |
| Equipment kinds | `ahu` |
| Operational gate | `fan_running` (startup 600s) |
| Default confirm | 600s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `clg_coil_enter_t` | `cooling-coil-entering-temp` | required |
| `clg_coil_leave_t` | `cooling-coil-leaving-temp` | required |
| `oa_damper_pct` | `outside-air-damper` | required |
| `clg_valve_pct` | `cooling-valve` | required |

#### Plot series

- `clg_coil_enter_t` → `cooling-coil-entering-temp`
- `clg_coil_leave_t` → `cooling-coil-leaving-temp`
- `oa_damper_pct` → `outside-air-damper`
- `clg_valve_pct` → `cooling-valve`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Fault hours / % on Results + FDD DOCX card; RCx overlays only if roles match a preset.

### `FC15` — HW coil ΔT when inactive (GL36 M)

**Equation:** Heating coil ΔT ≥ √(1.15²+1.15²)+0.55°F while coil should be inactive.

| Field | Value |
| --- | --- |
| Family | `ahu` |
| Equipment kinds | `ahu` |
| Operational gate | `fan_running` (startup 600s) |
| Default confirm | 600s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `htg_coil_enter_t` | `heating-coil-entering-temp` | required |
| `htg_coil_leave_t` | `heating-coil-leaving-temp` | required |
| `oa_damper_pct` | `outside-air-damper` | required |
| `clg_valve_pct` | `cooling-valve` | required |

#### Plot series

- `htg_coil_enter_t` → `heating-coil-entering-temp`
- `htg_coil_leave_t` → `heating-coil-leaving-temp`
- `oa_damper_pct` → `outside-air-damper`
- `clg_valve_pct` → `cooling-valve`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Fault hours / % on Results + FDD DOCX card; RCx overlays only if roles match a preset.

### `AHU-SATDEV` — SAT deviation from setpoint

**Equation:** |SAT − SAT SP| > 5°F.

| Field | Value |
| --- | --- |
| Family | `ahu` |
| Equipment kinds | `ahu` |
| Operational gate | `fan_running` (startup 600s) |
| Default confirm | 600s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `sat` | `discharge-air-temp` | required |
| `sat_sp` | `discharge-air-temp-sp` | required |

#### Plot series

- `sat` → `discharge-air-temp`
- `sat_sp` → `discharge-air-temp-sp`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `sat_dev_err` | SAT deviation | °F | 5 | 1 | 15 | 0.5 |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

RCx `ahu_sat_reset_scatter` — SAT vs web OAT.

### `AHU-DUCTHI` — Duct static pressure high

**Equation:** Duct static > static SP + 0.25 in.w.c.

| Field | Value |
| --- | --- |
| Family | `ahu` |
| Equipment kinds | `ahu` |
| Operational gate | `fan_running` (startup 300s) |
| Default confirm | 300s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `duct_static` | `duct-static-pressure` | required |
| `duct_static_sp` | `duct-static-pressure-sp` | required |

#### Plot series

- `duct_static` → `duct-static-pressure`
- `duct_static_sp` → `duct-static-pressure-sp`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `duct_high_margin` | High margin | in. w.c. | 0.25 | 0.05 | 1 | 0.05 |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

RCx `duct_static_box` (fan-on) for static-reset opportunity.

### `AHU-SIMUL` — Heating and cooling simultaneous

**Equation:** Heating valve > 10% AND cooling valve > 10% at once.

| Field | Value |
| --- | --- |
| Family | `ahu` |
| Equipment kinds | `ahu` |
| Operational gate | `fan_running` (startup 300s) |
| Default confirm | 300s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `htg_valve_pct` | `heating-valve` | required |
| `clg_valve_pct` | `cooling-valve` | required |

#### Plot series

- `htg_valve_pct` → `heating-valve`
- `clg_valve_pct` → `cooling-valve`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `valve_open_pct` | Valve open threshold | frac | 0.1 | 0.05 | 0.5 | 0.01 |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Fault hours / % on Results + FDD DOCX card; RCx overlays only if roles match a preset.

### `OAT-METEO` — BAS outdoor-air sensor vs Open-Meteo

**Equation:** BAS OAT sensor differs from Open-Meteo dry bulb by more than 5°F.

| Field | Value |
| --- | --- |
| Family | `ahu` |
| Equipment kinds | `ahu` |
| Operational gate | `always` |
| Default confirm | 900s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `oa_t` | `outside-air-temp` | required |
| `wx_oa_t` | `web-outside-air-temp` | required |

#### Plot series

- `oa_t` → `outside-air-temp`
- `wx_oa_t` → `web-outside-air-temp`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `oat_err` | Max OAT disagreement | °F | 5 | 2 | 20 | 0.5 |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Needs both BAS `oa_t` and web `wx_oa_t`; Prefer web OAT sidebar.

### `ECON-1` — Economizer stuck closed

**Equation:** Fan on, OA damper < 5%, OAT > 55°F (should be economizing).

| Field | Value |
| --- | --- |
| Family | `ahu` |
| Equipment kinds | `ahu` |
| Operational gate | `fan_running` (startup 600s) |
| Default confirm | 600s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `fan_cmd` | `fan-cmd` | required |
| `oa_damper_pct` | `outside-air-damper` | required |
| `oa_t` | `outside-air-temp` | required |

#### Plot series

- `fan_cmd` → `fan-cmd`
- `oa_damper_pct` → `outside-air-damper`
- `oa_t` → `outside-air-temp`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `econ1_oat_min` | Favorable OAT | °F | 55 | 45 | 70 | 1 |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Needs OA damper / MAT / OAT roles (`oa_damper_pct` e.g. mad_c).

### `ECON-2` — Economizing when outdoor unfavorable

**Equation:** OAT > 63°F AND OA damper > 42% (should be at minimum).

| Field | Value |
| --- | --- |
| Family | `ahu` |
| Equipment kinds | `ahu` |
| Operational gate | `fan_running` (startup 300s) |
| Default confirm | 300s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `oa_t` | `outside-air-temp` | required |
| `oa_damper_pct` | `outside-air-damper` | required |

#### Plot series

- `oa_t` → `outside-air-temp`
- `oa_damper_pct` → `outside-air-damper`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `econ2_oat_hi` | OAT high cutoff | °F | 63 | 55 | 80 | 1 |
| `econ2_damper` | Damper open frac | frac | 0.42 | 0.2 | 0.9 | 0.02 |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Needs OA damper / MAT / OAT roles.

### `ECON-3` — Mech cooling when econ available

**Equation:** Free cooling available when web dry-bulb is 35–72°F AND dewpoint < 60°F (RH→dewpoint if needed); fault when cooling valve open with OA damper closed. Optional SAT≈SP means free cooling is keeping up.

| Field | Value |
| --- | --- |
| Family | `ahu` |
| Equipment kinds | `ahu` |
| Operational gate | `fan_running` (startup 600s) |
| Default confirm | 300s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `oa_damper_pct` | `outside-air-damper` | required |
| `clg_valve_pct` | `cooling-valve` | required |

#### Plot series

- `oa_damper_pct` → `outside-air-damper`
- `clg_valve_pct` → `cooling-valve`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `econ3_db_min` | Free-cool OA dry-bulb min | °F | 35 | 25 | 45 | 1 |
| `econ3_db_max` | Free-cool OA dry-bulb max | °F | 72 | 60 | 80 | 1 |
| `econ3_dp_max` | Free-cool OA dew point max | °F | 60 | 45 | 68 | 1 |
| `econ3_oat_fallback` | Fallback OAT cutoff | °F | 63 | 55 | 70 | 1 |
| `econ3_damper` | Damper closed frac | frac | 0.32 | 0.1 | 0.6 | 0.02 |
| `econ3_zone_band` | SAT≈SP band (keeping up) | °F | 2 | 0.5 | 6 | 0.5 |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Free-cool uses web dry-bulb + dewpoint (RH→Magnus); related to mech-cooling OAT bins (DX/plant only).

### `ECON-4` — Low estimated OA fraction

**Equation:** Fan on, |RAT−OAT| > 2.2°F, estimated OA fraction < 21%.

| Field | Value |
| --- | --- |
| Family | `ahu` |
| Equipment kinds | `ahu` |
| Operational gate | `fan_running` (startup 600s) |
| Default confirm | 600s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `mat` | `mixed-air-temp` | required |
| `rat` | `return-air-temp` | required |
| `oa_t` | `outside-air-temp` | required |
| `fan_cmd` | `fan-cmd` | required |

#### Plot series

- `mat` → `mixed-air-temp`
- `rat` → `return-air-temp`
- `oa_t` → `outside-air-temp`
- `fan_cmd` → `fan-cmd`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `oa_min_pct` | Min OA fraction | % | 21 | 5 | 40 | 1 |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Needs OA damper / MAT / OAT roles.

### `ECON-5` — Preheat over-conditioning

**Equation:** Preheat leaving air > 2.2°F above target while preheat active.

| Field | Value |
| --- | --- |
| Family | `ahu` |
| Equipment kinds | `ahu` |
| Operational gate | `fan_running` (startup 600s) |
| Default confirm | 600s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `preheat_leave_t` | `preheat-leaving-temp` | required |
| `sat_sp` | `discharge-air-temp-sp` | required |
| `oa_t` | `outside-air-temp` | required |
| `htg_valve_pct` | `heating-valve` | required |

#### Plot series

- `preheat_leave_t` → `preheat-leaving-temp`
- `sat_sp` → `discharge-air-temp-sp`
- `oa_t` → `outside-air-temp`
- `htg_valve_pct` → `heating-valve`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Needs heat/preheat roles.

### `SCHED-1` — Unoccupied runtime

**Equation:** Fan running while occupancy is unoccupied (Overview calendar → occ_mode). When zone_t is mapped, also require zone inside comfort_low_f…comfort_high_f (defaults 70–76°F; synced from Overview zone band).

| Field | Value |
| --- | --- |
| Family | `ahu` |
| Equipment kinds | `ahu` |
| Operational gate | `always` |
| Default confirm | 1800s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `occ_mode` | `occupied` | required |
| `fan_status` | `fan-status` | required |
| `zone_t` | `zone-air-temp` | optional |

#### Plot series

- `occ_mode` → `occupied`
- `fan_status` → `fan-status`
- `zone_t` → `zone-air-temp`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `comfort_low_f` | Comfort low | °F | 70 | 60 | 78 | 0.5 |
| `comfort_high_f` | Comfort high | °F | 76 | 68 | 85 | 0.5 |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Overview occupancy calendar drives `occ_mode`; zone comfort band sliders (°F/°C display).

### `CMD-1` — Fan cmd/status mismatch

**Equation:** Fan command and proven status disagree.

| Field | Value |
| --- | --- |
| Family | `ahu` |
| Equipment kinds | `ahu` |
| Operational gate | `always` |
| Default confirm | 600s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `fan_cmd` | `fan-cmd` | required |
| `fan_status` | `fan-status` | required |

#### Plot series

- `fan_cmd` → `fan-cmd`
- `fan_status` → `fan-status`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Fault hours / % on Results + FDD DOCX card; RCx overlays only if roles match a preset.

### `OA-1` — Low OA fraction

**Equation:** Estimated OA fraction < 15% with adequate OAT/RAT split.

| Field | Value |
| --- | --- |
| Family | `ahu` |
| Equipment kinds | `ahu` |
| Operational gate | `fan_running` (startup 600s) |
| Default confirm | 900s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `mat` | `mixed-air-temp` | required |
| `rat` | `return-air-temp` | required |
| `oa_t` | `outside-air-temp` | required |
| `fan_status` | `fan-status` | required |

#### Plot series

- `mat` → `mixed-air-temp`
- `rat` → `return-air-temp`
- `oa_t` → `outside-air-temp`
- `fan_status` → `fan-status`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `min_oa_frac` | Min OA fraction | frac | 0.15 | 0.05 | 0.4 | 0.01 |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Fault hours / % on Results + FDD DOCX card; RCx overlays only if roles match a preset.

### `DMP-1` — OA damper leakage

**Equation:** Damper ≤ 5% but MAT tracks OAT within 2°F — leaking OA damper.

| Field | Value |
| --- | --- |
| Family | `ahu` |
| Equipment kinds | `ahu` |
| Operational gate | `conditional` (startup 300s) |
| Default confirm | 900s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `oa_t` | `outside-air-temp` | required |
| `mat` | `mixed-air-temp` | required |
| `oa_damper_pct` | `outside-air-damper` | required |

#### Plot series

- `oa_t` → `outside-air-temp`
- `mat` → `mixed-air-temp`
- `oa_damper_pct` → `outside-air-damper`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `leak_delta` | Leak ΔT | °F | 2 | 0.5 | 6 | 0.5 |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Fault hours / % on Results + FDD DOCX card; RCx overlays only if roles match a preset.

### `VLV-1` — Cooling valve leakage

**Equation:** Cooling valve ≤ 5% AND (SAT < sat_sp − sat_err OR SAT < MAT − mat_leak_delta). Fan proven on when fan_status/fan_cmd present (operational gate).

| Field | Value |
| --- | --- |
| Family | `ahu` |
| Equipment kinds | `ahu` |
| Operational gate | `conditional` (startup 300s) |
| Default confirm | 900s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `sat` | `discharge-air-temp` | required |
| `sat_sp` | `discharge-air-temp-sp` | required |
| `clg_valve_pct` | `cooling-valve` | required |
| `mat` | `mixed-air-temp` | optional |
| `fan_status` | `fan-status` | optional |
| `fan_cmd` | `fan-cmd` | optional |

#### Plot series

- `sat` → `discharge-air-temp`
- `sat_sp` → `discharge-air-temp-sp`
- `clg_valve_pct` → `cooling-valve`
- `mat` → `mixed-air-temp`
- `fan_status` → `fan-status`
- `fan_cmd` → `fan-cmd`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `sat_err` | SAT vs SP leak ΔT | °F | 2 | 0.5 | 8 | 0.5 |
| `mat_leak_delta` | SAT vs MAT leak ΔT | °F | 2 | 0.5 | 12 | 0.5 |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Valve closed + SAT vs SP **or** SAT vs MAT; fan gate when present.


---

## 4 · VAV / terminal

### `VAV-1` — Zone comfort band

**Equation:** Zone temp < 68°F or > 76°F.

| Field | Value |
| --- | --- |
| Family | `vav` |
| Equipment kinds | `vav`, `zone` |
| Operational gate | `conditional` |
| Default confirm | 900s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `zone_t` | `zone-air-temp` | required |

#### Plot series

- `zone_t` → `zone-air-temp`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `zone_lo` | Zone low | °F | 68 | 55 | 70 | 0.5 |
| `zone_hi` | Zone high | °F | 76 | 72 | 85 | 0.5 |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Fault hours / % on Results + FDD DOCX card; RCx overlays only if roles match a preset.

### `VAV-3` — Excessive reheat during warm weather

**Equation:** Air flowing AND OAT > 78°F AND reheat valve > 52%.

| Field | Value |
| --- | --- |
| Family | `vav` |
| Equipment kinds | `vav` |
| Operational gate | `fan_running` (startup 300s) |
| Default confirm | 300s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `oa_t` | `outside-air-temp` | required |
| `reheat_valve_pct` | `reheat-valve` | required |

#### Plot series

- `oa_t` → `outside-air-temp`
- `reheat_valve_pct` → `reheat-valve`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `reheat_oat` | Warm OAT | °F | 78 | 65 | 90 | 1 |
| `reheat_pct` | Reheat frac | frac | 0.52 | 0.1 | 1 | 0.02 |
| `flow_on_min` | Airflow-on min | cfm | 25 | 0 | 200 | 5 |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Fault hours / % on Results + FDD DOCX card; RCx overlays only if roles match a preset.

### `VAV-4` — Damper stuck at full open

**Equation:** Air flowing AND damper > 97.5% sustained across the window.

| Field | Value |
| --- | --- |
| Family | `vav` |
| Equipment kinds | `vav` |
| Operational gate | `control_loop` (startup 300s) |
| Default confirm | 900s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `damper_pct` | `damper` | required |

#### Plot series

- `damper_pct` → `damper`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `full_open_pct` | Full open frac | frac | 0.975 | 0.8 | 1 | 0.005 |
| `sustain_hours` | Sustain window | h | 1.5 | 0.5 | 6 | 0.5 |
| `flow_on_min` | Airflow-on min | cfm | 25 | 0 | 200 | 5 |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Fault hours / % on Results + FDD DOCX card; RCx overlays only if roles match a preset.

### `VAV-5` — Airflow sensor bias

**Equation:** Airflow > 50 cfm while damper < 10% (implausible flow).

| Field | Value |
| --- | --- |
| Family | `vav` |
| Equipment kinds | `vav` |
| Operational gate | `fan_running` (startup 300s) |
| Default confirm | 900s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `zone_flow` | `zone-airflow` | required |
| `damper_pct` | `damper` | required |

#### Plot series

- `zone_flow` → `zone-airflow`
- `damper_pct` → `damper`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Fault hours / % on Results + FDD DOCX card; RCx overlays only if roles match a preset.

### `VAV-REHEAT` — Reheat valve stuck / no temp rise

**Equation:** Air flowing AND reheat valve > 30% AND box discharge temp rises < 3°F above duct inlet (air from AHU) — stuck or failed reheat valve/coil.

| Field | Value |
| --- | --- |
| Family | `vav` |
| Equipment kinds | `vav` |
| Operational gate | `fan_running` (startup 600s) |
| Default confirm | 900s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `reheat_valve_pct` | `reheat-valve` | required |
| `vav_disch_t` | `vav-discharge-air-temp` | required |
| `vav_inlet_t` | `vav-inlet-air-temp` | required |

#### Plot series

- `reheat_valve_pct` → `reheat-valve`
- `vav_disch_t` → `vav-discharge-air-temp`
- `vav_inlet_t` → `vav-inlet-air-temp`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `reheat_cmd` | Reheat open frac | frac | 0.3 | 0.1 | 1 | 0.05 |
| `min_rise` | Min temp rise | °F | 3 | 0.5 | 15 | 0.5 |
| `flow_on_min` | Airflow-on min | cfm | 25 | 0 | 200 | 5 |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Fault hours / % on Results + FDD DOCX card; RCx overlays only if roles match a preset.

### `VAV-7` — Min airflow / fixed high flow

**Equation:** Flow below min SP (when mapped), OR airflow stays flat (low rolling std) at a high mean while air is on (mins too high / box never modulates), OR min_flow_sp itself is excessively high.

| Field | Value |
| --- | --- |
| Family | `vav` |
| Equipment kinds | `vav` |
| Operational gate | `fan_running` (startup 300s) |
| Default confirm | 900s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `zone_flow` | `zone-airflow` | required |

#### Plot series

- `zone_flow` → `zone-airflow`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `flow_on_min` | Airflow-on min | cfm | 25 | 0 | 200 | 5 |
| `fixed_flow_max_std` | Fixed-flow max std | cfm | 15 | 1 | 80 | 1 |
| `fixed_flow_min_mean` | Fixed-flow min mean | cfm | 200 | 50 | 2000 | 10 |
| `high_min_flow_sp` | High min-flow SP | cfm | 250 | 50 | 2000 | 10 |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Fault hours / % on Results + FDD DOCX card; RCx overlays only if roles match a preset.


---

## 5 · Central plant

### `CHW-1` — Low chilled-water ΔT

**Equation:** Pump on AND (CHWR − CHWS) < 4°F.

| Field | Value |
| --- | --- |
| Family | `plant` |
| Equipment kinds | `chiller` |
| Operational gate | `hydronic_flow` (startup 900s) |
| Default confirm | 900s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `chw_supply_t` | `chilled-water-supply-temp` | required |
| `chw_return_t` | `chilled-water-return-temp` | required |

#### Plot series

- `chw_supply_t` → `chilled-water-supply-temp`
- `chw_return_t` → `chilled-water-return-temp`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `min_dt` | Min ΔT | °F | 4 | 1 | 12 | 0.5 |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

RCx `chw_reset_scatter` — CHW leave vs web OAT; motor weekly uses pump/status not leave-temp.

### `CHW-2` — DP below SP at max pump speed

**Equation:** Pump ≥ 87% AND CHW DP < DP SP − 2.2.

| Field | Value |
| --- | --- |
| Family | `plant` |
| Equipment kinds | `chiller` |
| Operational gate | `hydronic_flow` (startup 300s) |
| Default confirm | 300s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `chw_dp` | `chw-diff-pressure` | required |
| `chw_dp_sp` | `chw-diff-pressure-sp` | required |
| `chw_pump_cmd` | `chw-pump-cmd` | required |

#### Plot series

- `chw_dp` → `chw-diff-pressure`
- `chw_dp_sp` → `chw-diff-pressure-sp`
- `chw_pump_cmd` → `chw-pump-cmd`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `dp_margin` | DP margin | psi | 2.2 | 0.5 | 6 | 0.1 |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Plant motor weekly / chiller runtime — status/pump proof.

### `CHW-3` — Plant supply temp outside deadband

**Equation:** Pump on AND |CHWS − CHWS SP| > 2.2°F.

| Field | Value |
| --- | --- |
| Family | `plant` |
| Equipment kinds | `chiller` |
| Operational gate | `hydronic_flow` (startup 600s) |
| Default confirm | 300s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `chw_supply_t` | `chilled-water-supply-temp` | required |
| `chw_supply_t_sp` | `chilled-water-supply-temp-sp` | required |
| `chw_pump_cmd` | `chw-pump-cmd` | required |

#### Plot series

- `chw_supply_t` → `chilled-water-supply-temp`
- `chw_supply_t_sp` → `chilled-water-supply-temp-sp`
- `chw_pump_cmd` → `chw-pump-cmd`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `sp_band` | SP band | °F | 2.2 | 0.5 | 6 | 0.1 |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Fault hours / % on Results + FDD DOCX card; RCx overlays only if roles match a preset.

### `CHW-4` — Flow high at max pump

**Equation:** Pump ≥ 87% AND CHW flow > 1100 gpm.

| Field | Value |
| --- | --- |
| Family | `plant` |
| Equipment kinds | `chiller` |
| Operational gate | `hydronic_flow` (startup 300s) |
| Default confirm | 300s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `chw_flow` | `chw-flow` | required |
| `chw_pump_cmd` | `chw-pump-cmd` | required |

#### Plot series

- `chw_flow` → `chw-flow`
- `chw_pump_cmd` → `chw-pump-cmd`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `flow_hi` | Flow high | gpm | 1100 | 200 | 3000 | 50 |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Fault hours / % on Results + FDD DOCX card; RCx overlays only if roles match a preset.

### `CW-OPT-1` — Condenser water not optimized vs wet-bulb

**Equation:** CW supply significantly colder than web wet-bulb + design approach (Stull WB) — tower over-cooling / not optimized.

| Field | Value |
| --- | --- |
| Family | `plant` |
| Equipment kinds | `chiller` |
| Operational gate | `hydronic_flow` (startup 600s) |
| Default confirm | 900s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `cw_supply_t` | `condenser-water-supply-temp` | required |

#### Plot series

- `cw_supply_t` → `condenser-water-supply-temp`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `cw_approach` | Design approach | °F | 7 | 3 | 15 | 0.5 |
| `cw_slack` | Slack below target | °F | 2 | 0.5 | 6 | 0.5 |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

RCx `cw_reset_scatter` uses `cw_supply_t` vs web wet-bulb.


---

## 6 · Heat pump

### `HP-1` — Discharge cold when heating

**Equation:** Fan on, zone < 69°F, discharge SAT < 85°F.

| Field | Value |
| --- | --- |
| Family | `heatpump` |
| Equipment kinds | `heatpump` |
| Operational gate | `compressor` (startup 600s) |
| Default confirm | 600s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `sat` | `discharge-air-temp` | required |
| `zone_t` | `zone-air-temp` | required |
| `fan_cmd` | `fan-cmd` | required |

#### Plot series

- `sat` → `discharge-air-temp`
- `zone_t` → `zone-air-temp`
- `fan_cmd` → `fan-cmd`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `min_sat` | Min heating SAT | °F | 85 | 70 | 110 | 1 |
| `zone_cold` | Zone cold | °F | 69 | 60 | 72 | 0.5 |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Mech-cooling OAT bins can use DX/compressor roles.


---

## 7 · Weather / OAT

### `WX-1` — OA temperature spike

**Equation:** OAT sample-to-sample jump > 16°F.

| Field | Value |
| --- | --- |
| Family | `weather` |
| Equipment kinds | `weather` |
| Operational gate | `always` |
| Default confirm | 300s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `oa_t` | `outside-air-temp` | required |

#### Plot series

- `oa_t` → `outside-air-temp`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `spike_limit` | Spike limit | °F | 16 | 4 | 40 | 1 |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Weather family; web OAT enrich on weather frame.


---

## 8 · Trim & respond

### `TRIM-1` — Duct static trim advisory

**Equation:** Duct static high (> 1.35 in.w.c.) while VAV pressure requests are low.

| Field | Value |
| --- | --- |
| Family | `trim` |
| Equipment kinds | `ahu` |
| Operational gate | `fan_running` (startup 300s) |
| Default confirm | 1800s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `duct_static` | `duct-static-pressure` | required |
| `vav_press_req_sum` | `vav-pressure-request-sum` | required |

#### Plot series

- `duct_static` → `duct-static-pressure`
- `vav_press_req_sum` → `vav-pressure-request-sum`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

Duct static / pressure trim requests; related to duct-static box RCx.

### `TRIM-3` — HWST trim advisory

**Equation:** HW supply > 160°F while reset requests are low.

| Field | Value |
| --- | --- |
| Family | `trim` |
| Equipment kinds | `boiler` |
| Operational gate | `hydronic_flow` (startup 600s) |
| Default confirm | 1800s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `hw_supply_t` | `hot-water-supply-temp` | required |
| `hw_reset_req_sum` | `hw-reset-request-sum` | required |

#### Plot series

- `hw_supply_t` → `hot-water-supply-temp`
- `hw_reset_req_sum` → `hw-reset-request-sum`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

HW reset requests; RCx `hw_reset_scatter`.

### `TRIM-4` — CHW plant reset advisory

**Equation:** CHW supply < 45°F while reset requests are low.

| Field | Value |
| --- | --- |
| Family | `trim` |
| Equipment kinds | `chiller` |
| Operational gate | `hydronic_flow` (startup 600s) |
| Default confirm | 1800s |
| Sweep | — |

#### Points → Haystack tags (this chart)

| Cookbook role | Haystack-like tag | Requirement |
| --- | --- | --- |
| `chw_supply_t` | `chilled-water-supply-temp` | required |
| `chw_reset_req_sum` | `chw-reset-request-sum` | required |

#### Plot series

- `chw_supply_t` → `chilled-water-supply-temp`
- `chw_reset_req_sum` → `chw-reset-request-sum`
- `confirmed_fault` swim lane (bool shade) when the rule was run

#### Sliders (tune params)

| Key | Label | Unit | Default | Min | Max | Step |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `confirm_min` | Fault confirm delay | min | 5 | 0 | 60 | 1 |

#### Analytics / related views

CHW reset requests; RCx `chw_reset_scatter`.

---

## Appendix A — `COOKBOOK_TO_HAYSTACK_POINT` (canonical export)

| Cookbook role | Haystack-like tag |
| --- | --- |
| `chw_dp` | `chw-diff-pressure` |
| `chw_dp_sp` | `chw-diff-pressure-sp` |
| `chw_flow` | `chw-flow` |
| `chw_pump_cmd` | `chw-pump-cmd` |
| `chw_reset_req_sum` | `chw-reset-request-sum` |
| `chw_return_t` | `chilled-water-return-temp` |
| `chw_supply_t` | `chilled-water-supply-temp` |
| `chw_supply_t_sp` | `chilled-water-supply-temp-sp` |
| `clg_coil_enter_t` | `cooling-coil-entering-temp` |
| `clg_coil_leave_t` | `cooling-coil-leaving-temp` |
| `clg_valve_pct` | `cooling-valve` |
| `cw_supply_t` | `condenser-water-supply-temp` |
| `damper_pct` | `damper` |
| `duct_static` | `duct-static-pressure` |
| `duct_static_sp` | `duct-static-pressure-sp` |
| `fan_cmd` | `fan-cmd` |
| `fan_status` | `fan-status` |
| `htg_coil_enter_t` | `heating-coil-entering-temp` |
| `htg_coil_leave_t` | `heating-coil-leaving-temp` |
| `htg_valve_pct` | `heating-valve` |
| `hw_reset_req_sum` | `hw-reset-request-sum` |
| `hw_return_t` | `hot-water-return-temp` |
| `hw_supply_t` | `hot-water-supply-temp` |
| `loop_enabled` | `loop-enabled` |
| `mat` | `mixed-air-temp` |
| `min_flow_sp` | `min-flow-sp` |
| `oa_damper_pct` | `outside-air-damper` |
| `oa_t` | `outside-air-temp` |
| `occ_mode` | `occupied` |
| `preheat_leave_t` | `preheat-leaving-temp` |
| `rat` | `return-air-temp` |
| `reheat_valve_pct` | `reheat-valve` |
| `sat` | `discharge-air-temp` |
| `sat_sp` | `discharge-air-temp-sp` |
| `vav_disch_t` | `vav-discharge-air-temp` |
| `vav_inlet_t` | `vav-inlet-air-temp` |
| `vav_press_req_sum` | `vav-pressure-request-sum` |
| `vav_total_flow` | `vav-total-airflow` |
| `wx_oa_t` | `web-outside-air-temp` |
| `zone_flow` | `zone-airflow` |
| `zone_t` | `zone-air-temp` |

## Appendix B — Extended Haystack-style names used in this catalog

These roles appear on rules but are **not** yet keys in `COOKBOOK_TO_HAYSTACK_POINT`.
Prefer adding them to the dict when you next touch mapping exports.

| Cookbook role | Suggested Haystack-like tag |
| --- | --- |
| `airflow_proof` | `airflow-proof` |
| `compressor_status` | `compressor-status` |
| `cool_stage` | `cool-stage` |
| `dx_cool_cmd` | `dx-cool-cmd` |
| `dx_cooling` | `dx-cooling` |
| `dx_stage` | `dx-stage` |
| `fan_current` | `fan-current` |
| `fan_power` | `fan-power` |
| `fan_speed_feedback` | `fan-speed-feedback` |
| `pump_status` | `pump-status` |

## Appendix C — Related RCx presets (not the 50)

See [`RCX_PLOTS.md`](RCX_PLOTS.md). Reset scatters / duct-static box share roles with plant/AHU rules above.

## Appendix D — Building-level analytics (not per-rule charts)

| View | Where | Roles / inputs |
| --- | --- | --- |
| Motor weekly runtime | Overview / Analytics | fan/pump/compressor **status** preferred |
| Mech-cooling OAT bins | Overview / Analytics | plant pump/status or DX compressor; **web OAT**; never CHW valve % |
| Sensor fault summary | Plots (device) | sensors involved in FAULT SV-* |
| Occupancy calendar | Overview | writes `occ_mode` for SCHED-1 |

