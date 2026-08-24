# Vibe Code App 23 — LBNL Building 59 EnergyPlus Calibration + DSM Lab

Vibe 23 starts a clean public-data EnergyPlus calibration case study using **Lawrence Berkeley National Laboratory Building 59 (Shyh Wang Hall)** in Berkeley, California.

**Current status:** `CALIBRATION_BOOTSTRAP` — this is not yet a calibrated EnergyPlus model. The first milestone provides reproducible data acquisition, file/point inventory, measured-power aggregation, calibration metrics, an evidence ledger, and the agent/build specification needed to construct the model without inventing facts.

## Public source

- Dryad DOI: `10.7941/D1N33Q`
- Dryad release: `Building_59.zip` (~263 MB compressed; ~2.38 GB time-series data uncompressed)
- 27 cleaned CSV files / 337 data points reported by the publication
- Three years of whole-building/end-use energy, HVAC, environment and occupancy data

The dataset publication describes a four-floor, 10,400 m² conditioned building. The top two office floors use underfloor air distribution and are served by four rooftop units. The dataset itself reports monitored coverage of two office floors at 2,325 m² each. Vibe 23 records this area discrepancy explicitly instead of silently choosing one geometry number.

## Quick start

```bash
cd vibe_code_apps_23
python -m pip install -e ".[dev]"

# Download + safely extract the Dryad package. Raw telemetry stays gitignored.
vibe23 download --data-dir data

# Inventory the real CSV package before binding any point names.
vibe23 inventory --root data/raw/building_59 --out data/processed/inventory.csv

# After selecting a real power point from metadata/inventory:
vibe23 aggregate-power \
  --csv path/to/source.csv \
  --timestamp-column timestamp \
  --value-column power_kw \
  --rule 1h \
  --out data/processed/measured_hourly.csv

# Score a table containing measured and simulated columns.
vibe23 score --csv comparison.csv --interval hourly
```

## Modeling plan
1. Download and inventory Building 59.
2. Bind whole-building meter, HVAC end uses, temperatures, airflow, occupancy and controls from source metadata.
3. Resolve the monitored-area vs full-office-area geometry discrepancy.
4. Build a two-office-floor EnergyPlus seed with the documented UFAD/RTU/UFT topology needed for controls research.
5. Use actual-year Berkeley weather aligned to a selected stable calibration year.
6. Calibrate schedules/base loads first, then envelope/ventilation, then HVAC efficiencies/controls.
7. Gate claims with monthly/hourly Guideline-14-style metrics plus peak demand, end-use and zone-temperature checks.
8. Research the historical utility tariff separately. Until account/rate assignment is proven, pricing remains candidate/illustrative.
9. After calibration, run transparent DSM comparators first; MPC/RL remain later options.

## Agent docs
- [`AGENTS.md`](AGENTS.md)
- [`vibe23_agent_spec/SPEC.md`](vibe23_agent_spec/SPEC.md)
- [`vibe23_agent_spec/DATA_CONTRACT.md`](vibe23_agent_spec/DATA_CONTRACT.md)
- [`vibe23_agent_spec/DSM_ROADMAP.md`](vibe23_agent_spec/DSM_ROADMAP.md)
- [`../agentic_ai/skills/README.md`](../agentic_ai/skills/README.md)

## Tariff honesty
Interval meter data can be aggregated into monthly kWh and monthly peak kW, but those are derived meter records, **not original utility invoices**. Do not claim an exact historical PG&E bill or Building 59 rate until the account/rate assignment is evidenced.
