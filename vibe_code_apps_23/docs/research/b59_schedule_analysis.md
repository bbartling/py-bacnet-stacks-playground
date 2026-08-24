# Building 59 telemetry schedule analysis

Status: `DIAGNOSTIC_PRIORS_ONLY — TIME BASIS AND CALIBRATION INPUTS NOT FROZEN`

Machine-readable result:
[`../../config/b59_schedule_priors.json`](../../config/b59_schedule_priors.json).

## Outcome

The acquired telemetry supports bounded 2018 office occupancy, lighting, MEL,
and HVAC schedule hypotheses, but it does **not** yet support one authoritative
EnergyPlus schedule. The principal finding is that timestamps cannot be treated
as one common local timezone:

- `occ.csv` and `ele.csv` have naive timestamps whose shapes align at zero raw
  lag. Their raw-hour timing aligns with the published 05:00 lighting and 07:00
  MEL rise only under a candidate UTC-naive interpretation.
- 2018 `wifi.csv` aligns to occupancy/MEL only after an approximately 6–7 hour
  shift and behaves like a different clock convention.
- `rtu_fan_spd.csv` is nearly flat and nonzero at every 2018 raw hour, so its
  feedback values do not reveal an on/off availability schedule.

These are hypotheses to resolve against metadata/BAS exports. No timezone was
assigned or converted in the published artifact.

## Sources and integrity

| Source | SHA-256 |
| --- | --- |
| `Building_59.zip` | `1e224dd7479bb196a8e0368fceb70aa6f699c1d39e1e895ceba7f3b25150b1b4` |
| `occ.csv` | `3733f1ee535ef35a34eaa8b0dc0e45ab92fe64a7927ad18b8694d2ad512a9c06` |
| `wifi.csv` | `20185c346147642e0150d6dc6c5442a15437fdf2c0d4671387812c811b10804b` |
| `rtu_fan_spd.csv` | `ab98ebb6f62dbce868b3b1a93e64a660b766cfabed409cf5d96a560e09c88ffc` |
| `ele.csv` | `f77a5462ad0d0ddd522fc5701f35e42b26d36888c35106ea940c55383e838411` |
| data-description workbook | `6cf5be4565afe60ab17500c0d65d769df14b61e0c6447a7ff6b161b9eac0e63a` |

The controlling external sources are the Dryad release
([DOI 10.7941/D1N33Q](https://doi.org/10.7941/D1N33Q)), its Scientific Data
descriptor ([DOI 10.1038/s41597-022-01257-x](https://doi.org/10.1038/s41597-022-01257-x)),
and the later LBNL field report
([DOI 10.20357/B72310](https://doi.org/10.20357/B72310)). The first two govern
2018–2020 interpretation; the later report supplies a later-period control
comparison, not a replacement historical schedule.

## Reproducible method

Hashes and source examples:

```bash
sha256sum \
  "data/raw/building_59/Bldg59_clean data/occ.csv" \
  "data/raw/building_59/Bldg59_clean data/wifi.csv" \
  "data/raw/building_59/Bldg59_clean data/rtu_fan_spd.csv" \
  "data/raw/building_59/Bldg59_clean data/ele.csv"

for f in occ.csv wifi.csv rtu_fan_spd.csv ele.csv; do
  p="data/raw/building_59/Bldg59_clean data/$f"
  sed -n '1,3p' "$p"
  tail -2 "$p"
done
```

The profile calculation used pandas with an exact parser **per file**:

```python
FORMATS = {
    "occ.csv": "%Y-%m-%d %H:%M:%S",
    "wifi.csv": "%Y/%m/%d %H:%M",
    "rtu_fan_spd.csv": "%Y-%m-%d %H:%M:%S",
    "ele.csv": "%Y/%m/%d %H:%M",
}

timestamp = pandas.to_datetime(raw["date"], format=FORMATS[file], errors="raise")
ambiguous = timestamp.duplicated(keep=False)
observed = raw.loc[~ambiguous].dropna(subset=[signal])
observed["date"] = timestamp.loc[observed.index].dt.date
observed["hour"] = timestamp.loc[observed.index].dt.hour
observed["daytype"] = numpy.where(
    timestamp.loc[observed.index].dt.dayofweek < 5, "weekday", "weekend"
)
day_hour = observed.groupby(["date", "daytype", "hour"])[signal].mean()
profile = day_hour.groupby(["daytype", "hour"]).median()
```

This gives each observed date/hour one value before taking the across-date
median, preventing one-minute signals from outweighing 15-minute signals.
Monday–Friday and Saturday–Sunday are literal raw-date classifications;
holidays were not removed. No interpolation, fill, resampling synthesis, or
timezone conversion was added. Ambiguous duplicated timestamps were excluded.

Important limitation: the distributed files are the publisher's **cleaned**
release. The workbook says the upstream curation used linear interpolation,
KNN, and matrix factorization. Reported raw missing rates include about 18.2%
for south lighting, 32.9% for south MEL, 19.7% for north MEL, and 14% for RTU
fan speed. This analysis performs no additional imputation, but the clean CSVs
do not identify every value filled upstream.

## Timestamp-semantics tests

| File | Coverage/cadence | Explicit zone? | DST and ordering evidence | Finding |
| --- | --- | --- | --- | --- |
| `occ.csv` | 2018-05-22 07:00 through 2019-02-21 10:12; exact one-minute cadence | No | No duplicates. 2018-11-04 has 1,440 unique records and one of every raw hour. | Not a civil-time fall-back series. Same raw clock family as electricity is plausible. |
| `wifi.csv` | 2018-05-22 through 2018-07-11 at 10 min; then a 579-day gap; 2020-02-10 through 2020-12-31 at 5 min | No | Twelve duplicate timestamps. 2020-11-01 repeats hour 01; 2020-03-08 still contains hour 02. | Source-specific/inconsistent DST behavior; not safe to merge on raw wall clock with occupancy. |
| `rtu_fan_spd.csv` | 2018-01-01 through 2021-01-01; mostly 1 min with 15-min blocks and many cadence/gap transitions | No | No duplicates; spring transition days keep 1,440 minutes. Fall days contain missing/15-min blocks rather than a repeat convention. | Time basis unresolved; signal quality also blocks on/off inference. |
| `ele.csv` | 2018-01-01 01:00 through 2021-01-01 00:00; mostly 15 min, with 5/10-min segments and 13 gaps over one day | No | No duplicates. Every 2018–2020 DST transition date has 96 quarter-hour rows and all 24 raw hours. | Fixed raw-clock grid, not civil DST timestamps. |

Cross-correlation used separately computed observed hourly means and integer
shifts from -12 through +12 hours over 2018-05-22 to 2018-07-11:

| Pair | Best shift applied to first series | Paired hours | Spearman | Pearson |
| --- | ---: | ---: | ---: | ---: |
| camera occupancy vs MEL total | 0 h | 1,173 | 0.716 | 0.821 |
| camera occupancy vs Wi-Fi office sum | -6 h | 1,223 | 0.780 | 0.878 |
| Wi-Fi office sum vs MEL total | +6 h | 1,174 | 0.717 | 0.864 |

The ±7-hour alternatives were near-ties for Wi-Fi. This supports, but does not
prove, a UTC-naive occupancy/electricity and local-naive Wi-Fi hypothesis. The
point-binding and EnergyPlus calendar contracts must resolve civil time, UTC,
DST, and local standard time before schedule use.

## 2018 weekday/weekend profiles

The detailed 24-hour arrays are in the JSON artifact. Active hours below use
the source-clock minimum + 20% of source-clock range diagnostic.

| Signal | 2018 slice | Weekday/weekend days | Source-clock shape | Weekend/weekday daily-mean ratio | Interpretation |
| --- | --- | ---: | --- | ---: | --- |
| Camera occupancy, two south halves | May 22–Dec 31 | 160 / 64 | Active raw hours 15–23; weekday median hourly peak 47.3 people | 0.041 | Timing prior only. Counts do not cover the north half or full office. |
| Wi-Fi, south third+fourth | May 22–Jul 11 | 37 / 14 | Active raw hours 08–17 above a roughly 62-device background; peak 190 devices | 0.572 absolute | Timing cross-check only. Devices are not people and 2018 coverage is only 51 summer days. |
| Median of four RTU supply-fan feedbacks | Full year | 261 / 104 | Weekday medians 73.4–76.0% at every raw hour; weekends comparable | 0.999 | Does not expose off/on schedule; feedback scale/off-state requires review. |
| South lighting | Full year with gaps | 250 / 98 | High raw hours 13–02 across midnight; weekday peak 4.17 kW | 0.171 | Candidate UTC-naive interpretation maps the rise near the published 05:00 timing. South only. |
| South MEL | Full year with gaps | 250 / 98 | Strong raw-hour afternoon/evening rise; weekday peak 7.97 kW | 0.459 | Retain large standby fraction. |
| North MEL | Full year with gaps | 250 / 98 | Higher base and later peak than south; weekday peak 21.79 kW | 0.710 | Do not force north and south onto one amplitude schedule. |
| MEL north+south | Full year with gaps | 250 / 98 | Active raw hours 15–00; weekday peak 29.71 kW | 0.653 | Candidate UTC-naive interpretation maps the rise near published 07:00. |

## Pandemic and coverage limits

Median weekday daily means make the regime change explicit:

| Signal | 2018 | 2019 | 2020 through Mar 17 | 2020 Mar 18–Dec 31 |
| --- | ---: | ---: | ---: | ---: |
| South lighting, kW | 2.244 | 2.700 | 2.048 | 0.561 |
| MEL north+south, kW | 17.368 | 17.929 | 9.054 | 2.207 |
| Four-RTU median supply-fan feedback, % | 74.919 | 75.461 | 78.766 | 84.759 |

Lighting and MEL fall sharply during shelter-in-place, while the fan-feedback
record rises rather than following occupancy. Therefore:

- 2020 is a disturbance/control-regime dataset, not a normal-office prior;
- fan feedback is not an occupancy proxy;
- Wi-Fi's long gap leaves no 2019 comparison and its 2020 segment crosses the
  pandemic, wildfire, late-summer RBC changes, and MPC windows;
- occupancy ends in February 2019, so it cannot validate post-conversion or
  2020 schedules.

## Published operator schedule versus measured operation

The direct later-period source states a weekday 05:00–22:00 occupied/operator
window in 2023, with RTUs off outside it unless setback calls occurred. That is
a valuable source fact for the later controls, but it is **not** a measured
2018–2020 availability schedule.

The historical fan-feedback CSV instead remains nonzero at all 24 source-clock
hours, with almost no weekday/weekend separation. Possible explanations include
continuous historical fan operation, a feedback encoding that does not expose
off state, source cleaning/imputation, or a different timestamp/control
semantics. This analysis cannot choose among them.

Accordingly, the JSON retains two discrete HVAC hypotheses:

1. `H1_2018_NONZERO_FEEDBACK_ALL_SOURCE_HOURS` — diagnostic continuous
   feedback, not proof of enablement.
2. `H2_LATER_2023_OPERATOR_SCHEDULE` — 05:00–22:00 weekday sensitivity, not
   historical proof.

Do not continuously tune between them. Resolve a historical enable/status point
or run them as separately named, bounded sensitivity cases before calibration.

## Bounded calibration priors

These priors are intentionally wider than the central profiles and remain
blocked until the time basis is frozen:

| Schedule | Central local-time hypothesis | Permitted bound | Amplitude/weekend bound |
| --- | --- | --- | --- |
| People | Weekday 07:00–18:00 | start 06:00–09:00; end 16:00–19:00 | weekend 0–0.15; no whole-office count amplitude without spatial reconciliation |
| South lighting | Weekday 05:00–18:00 | start 04:00–07:00; end 17:00–20:00 | weekend scale 0.05–0.30; peak multiplier 0.85–1.20 |
| MEL | Weekday 07:00–17:00 | start 06:00–09:00; end 16:00–19:00 | weekend scale 0.50–0.80; peak multiplier 0.70–1.20 |
| RTU availability | unresolved | discrete continuous-feedback vs later 05:00–22:00-plus-setback hypotheses | no continuous optimization until enable semantics resolve |

The local-time labels above are calibration hypotheses triangulated from raw
profiles and published timing. They are not authorized timestamp conversions.
Before entering an IDF, each schedule needs a ledger record containing the
selected point scope, timezone transform, DST/standard-time behavior, valid
period, holiday treatment, source hashes, and reviewer approval.

## No-false-calibration boundary

This work does not freeze measured targets, weather, occupancy, schedules, or
the IDF. It does not convert Wi-Fi devices to occupants, reconstruct north
lighting, undo upstream imputation, prove 2018 RTU enablement, or show that the
later 05:00–22:00 operator schedule applied historically. Open-FDD may review
change points and equipment states after exact role binding; it may not promote
these diagnostic priors directly into model parameters.

