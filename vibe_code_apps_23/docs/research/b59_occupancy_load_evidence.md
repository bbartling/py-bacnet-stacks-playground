# Building 59 occupancy and internal-load evidence

Status: `DIAGNOSTIC_EVIDENCE_AND_BOUNDED_PRIORS_ONLY`

Machine-readable evidence is in
[`../../config/b59_occupancy_load_evidence.json`](../../config/b59_occupancy_load_evidence.json).
It is produced by
[`../../scripts/analyze_b59_occupancy_loads.py`](../../scripts/analyze_b59_occupancy_loads.py)
from the acquired source release, without copying raw telemetry.

## Scope and evidence boundary

The [Building 59 dataset page](https://bbd.labworks.org/ds/bbd/lbnlbldg59)
states that the published data cover the two office floors.  Building 59 also
contains mechanical and NERSC/data-computing floors; those loads are not a
valid surrogate for the office-floor telemetry boundary.  The dataset page
describes BMS electricity, HVAC/lighting state, indoor and outdoor conditions,
occupant counts, and Wi-Fi devices.  This specific artifact audits only the
released `occ.csv`, `wifi.csv`, and `ele.csv` inputs needed to form
occupancy/internal-load priors.  It does not create or validate an HVAC
setpoint, ventilation, or EnergyPlus calibration target.

| Signal | Released columns used | Actual scope | Modeling use allowed |
| --- | --- | --- | --- |
| Camera occupancy | `occ_third_south`, `occ_fourth_south` | Southern portions of the two office floors | Timing/relative-activity evidence only; do not scale directly to whole-office people. |
| Wi-Fi | `wifi_third_south`, `wifi_fourth_south` | Connected south-office devices | Timing cross-check only; devices are not occupants and persistent devices form a large background. |
| Lighting | `lig_S` | South-wing panel only | South lighting schedule and standby/weekday/weekend sensitivity; do not invent north lighting. |
| MELs | `mels_S`, `mels_N` | Two plug panels | Keep north/south amplitudes distinct until panels map to modeled spaces. |

The release metadata calls the lighting system LED, while the companion source
description reports fixture/control details that still require reconciliation.
This schedule work makes no lighting-technology claim; it uses the panel shape
only.

## Reproducible extraction

```bash
python scripts/analyze_b59_occupancy_loads.py \
  --raw-root "data/raw/building_59/Bldg59_clean data" \
  --output config/b59_occupancy_load_evidence.json
```

The output stores SHA-256 hashes, row/coverage/cadence audits, raw-clock
profiles, and daily-median regime contrasts.  It adds no interpolation,
timezone conversion, gap fill, holiday closure assumption, or raw-data export.
For each source date/hour, native samples are first averaged and date-level
values are then combined with a median; this prevents one-minute camera data
from outweighing quarter-hour electrical data.  US federal holidays are a
diagnostic day type only—not evidence that the building was closed.

## Time basis is a gate, not a detail

The three files have naive timestamps with no UTC offset.  Their clock and DST
semantics cannot safely be treated as one common civil local time.  The
machine-readable output therefore labels hours as `SOURCE_CLOCK_NAIVE` and
includes native-clock lag checks rather than applying a conversion.  In the
2018 common period, camera occupancy and MEL shapes align near zero raw lag,
while the Wi-Fi shape aligns only after a roughly six-to-seven-hour shift.
That supports a clock-family hypothesis, but it does **not** prove UTC/local
semantics or authorize a conversion.  The input must be reconciled against
historical BAS metadata before any profile becomes an EnergyPlus schedule.

The release is already a curated dataset.  Its published curation used methods
including interpolation and matrix factorization.  This analysis adds no new
imputation, but individual curated values cannot be treated as independently
raw observations from the CSV alone.

## Observed schedule evidence and change points

The 2018 pre-pandemic profiles contain a non-zero MEL overnight base, higher
weekday MEL use, and lower but non-zero weekend use.  South lighting has a
substantially lower weekend level, but this is only the south panel.  Camera
counts cover only 2018-05-22 through 2019-02-21; Wi-Fi has a short 2018 summer
segment and a later 2020 segment.  Neither is a complete three-year people
record.

The script records the 2020-03-18 shelter-in-place split.  Lighting and MEL
daily medians fall sharply after that date, whereas camera data are absent and
Wi-Fi remains a device proxy.  Thus the post-change profile is useful for an
explicit pandemic/control-regime sensitivity, not for defining normal office
occupancy, plug, or lighting schedules.  A later office return, smoke-control
operation, and any MPC periods must be treated as separately named regimes.

## Required use in the EnergyPlus model

1. Freeze a per-file source-clock to EnergyPlus-calendar mapping, including
   DST/standard-time treatment, before assigning a schedule hour.
2. Map the southern camera coverage and the north/south panels to actual model
   zones.  Establish a count model before deriving people density or sensible/
   latent gains from the camera and Wi-Fi signals.
3. Use measured `lig_S`, `mels_S`, and `mels_N` shapes as bounded schedule
   hypotheses.  Retain observed standby loads and do not double `lig_S` to
   synthesize missing north lighting.
4. Pair schedule fits with actual zone temperature, CO2, RTU flow/fan,
   supply-air-temperature, and setpoint points from the dataset; a monthly kWh
   fit alone is not enough.  Those HVAC analytics require a separately
   reviewed point-role map.
5. Keep normal-operation, wildfire/smoke, HVAC-plant-change, and pandemic/MPC
   periods out of one undifferentiated calibration objective.

The artifact is evidence for a controlled calibration campaign, not a claim
that the model is ASHRAE Guideline 14 calibrated or that any 90.1 reference
describes the as-built building.
