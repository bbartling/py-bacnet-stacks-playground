# Poorly documented existing building

This synthetic example demonstrates a conceptual hypothesis study from sparse
inputs. It does not contain measured facts, interval data, or a savings claim.
Capacity, operating-hours, ventilation (including a zero-OA fault), and weather
extensions are tested as hypotheses.

Run the portable dry-run:

```powershell
wattlab explore-existing --config examples/poorly_documented_existing_building/config.yaml --dry-run --out .artifacts/existing-building
```

To use monthly bills, set `monthly_bills_path`. A study with bills is still not
`VALIDATED` unless a separate `holdout_period` is configured. Use `--live` only
where the resolved IDF, EPW, and EnergyPlus runtime are available.
