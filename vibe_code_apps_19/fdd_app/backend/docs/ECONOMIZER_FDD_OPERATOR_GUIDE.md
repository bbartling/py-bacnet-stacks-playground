# AHU Economizer Diagnostics — Operator Guide

Field reference for RCx technicians and energy engineers. Each fault includes what to check and why it matters.

## Point requirements

| Priority | Points |
|----------|--------|
| **Required** | Timestamp, fan command/status, OAT, RAT, MAT, SAT, OA damper command, cooling command |
| **Preferred** | SAT setpoint, OA min position, damper position feedback, weather reference |
| **Optional** | OA/RA humidity (enthalpy), return/exhaust damper, CO2, freeze stat, override signals |

If required points are missing, the rule status is **not_evaluated** — not a pass.

## Fault codes

### ECON_SENSOR_FAULT
**What:** OAT, RAT, MAT, or SAT is flatlined, out of range, implausible vs weather, or MAT outside the OAT/RAT envelope.

**Why it matters:** Bad sensors cause false economizer commands and mask real damper faults.

**Field checks:**
- Compare OAT to a handheld thermometer and weather station
- Verify MAT sensor is in the mixed-air stream, not in a stratified pocket
- Check SAT against discharge probe at coil outlet

---

### ECON_NOT_ECONOMIZING_WHEN_SHOULD
**What:** Cooling load exists, outdoor air is favorable (cool/dry-bulb), but OA damper stays near minimum.

**Why it matters:** Wasted mechanical cooling energy; compressor/CHW runtime when free cooling is available.

**Field checks:**
- Manually command OA damper — does it move?
- Verify economizer enable in BAS (not disabled, not locked out)
- Check high-limit and minimum OA setpoints
- Confirm OAT/RAT readings are believable

---

### ECON_ECONOMIZING_WHEN_SHOULD_NOT
**What:** OA is too hot, too cold, or otherwise unsuitable, but OA damper remains above minimum.

**Why it matters:** Excess heating/cooling load, comfort issues, freeze risk in cold weather.

**Field checks:**
- High-limit / low-limit setpoints
- Damper returns to minimum when OA is unfavorable
- Actuator linkage and spring return

---

### ECON_DAMPER_NOT_MODULATING / ECON_DAMPER_STUCK_OPEN / ECON_DAMPER_STUCK_CLOSED
**What:** Damper command changes but MAT does not respond, or damper stays at 0%, minimum, or 100% inappropriately.

**Why it matters:** Root cause for most economizer energy and ventilation faults.

**Field checks:**
- Command vs actual blade position (visual inspection)
- Actuator power, pneumatic pressure, or VFD signal
- Linkage pins, crank arms, binding
- Position feedback calibration (if separate from command)

**Note (Building 100):** Export uses command as damper proxy — field-verify movement.

---

### ECON_EXCESS_OA
**What:** OA above code/minimum when economizer is not suitable (heating season, hot/humid OA).

**Why it matters:** Higher heating and cooling energy; possible simultaneous heating/cooling at air handler.

**Field checks:**
- Minimum OA setpoint vs design/code
- Damper leakage at closed/minimum
- Return damper pairing on dual-damper systems

---

### ECON_LOW_OA_VENTILATION_RISK
**What:** OA damper below expected minimum during occupied fan operation.

**Why it matters:** **IAQ and code ventilation risk** — not just energy.

**Field checks:**
- Minimum OA airflow setpoint and damper position
- Blocked intake, closed fire/smoke damper upstream
- CO2 trends if available

---

### ECON_MAT_PLAUSIBILITY
**What:** Mixed air temperature does not sit between OAT and RAT during stable fan operation.

**Why it matters:** Indicates sensor or stratification problem — fix before blaming dampers.

**Field checks:**
- MAT probe location and length in mixed-air plenum
- Multiple MAT readings across the duct cross-section

---

### ECON_MECH_COOLING_DURING_FREE_COOLING
**What:** Cooling valve/compressor active while dry-bulb economizer is favorable and OA damper is not fully open.

**Why it matters:** Primary RCx savings metric — quantifies lost economizer hours.

**Field checks:**
- Same as “not economizing when should”
- Review SAT reset and G36/legacy economizer lockout logic
- Document avoidable CHW/compressor runtime for savings estimate

---

### ECON_ENTHALPY_NOT_EVALUATED
**What:** OA/RA humidity not in export — enthalpy economizer logic cannot run.

**Action:** Export humidity or enthalpy points to enable this diagnostic.

## Diagnostic hierarchy

1. Data quality and point mapping  
2. Sensor plausibility (MAT, OAT, RAT, SAT)  
3. Operating mode and economizer suitability  
4. Damper command/feedback  
5. Economizer performance faults  
6. Energy / IAQ impact  

When a sensor fault is active, downstream economizer faults may be downgraded to **possible** — verify sensors first.

## Configurable thresholds (defaults)

| Parameter | Default |
|-----------|---------|
| Resample interval | 15 min (Building 100 native) |
| Persistence | 15 min continuous |
| Temperature deadband | 2 °F |
| Damper deadband | 8 % |
| MAT envelope deadband | 2.5 °F |
| OAT favorable vs RAT | 3 °F cooler |
| Economizer high limit | 75 °F |
| Economizer low limit | 35 °F |
| Cooling active | CHW > 20 % |

Tune per site, climate zone, and control sequence.

## Known limitations (Building 100)

- No OA/RA humidity → enthalpy economizer not evaluated  
- No separate damper position feedback  
- No heating coil command in export  
- No CO2, freeze stat, or override signals  
- Damper % is **not** airflow % — treat estimated OA fraction as indicative only  

## Exports

- `economizer_diagnostics_summary_all.csv` — fault rollups per AHU  
- `economizer_fault_timeseries_ahu_*.csv` — timestamp-level flags for trending  
- `economizer_diagnostics.html` — interactive RCx view with plots  
