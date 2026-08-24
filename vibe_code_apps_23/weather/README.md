# Building 59 2020 screening weather

`b59_2020_bounded_hybrid_amy.epw` is intentionally ignored because it is a
generated 1.6 MB runtime input. Its portable provenance and expected SHA-256
are committed in `b59_2020_epw_manifest.json`.

The EPW contains 8,784 fixed-PST records for leap year 2020. Campus telemetry
provides dry bulb, dew point, relative humidity, and global horizontal solar
for 8,776 hours. The final eight hours use the explicit hashed substitution in
the manifest; other EPW fields use the documented Open-Meteo reanalysis source.
It is therefore a bounded hybrid AMY for screening, not a pure site-weather
record suitable for an unqualified calibration claim.

Reproduce the saved auxiliary inputs and then build the EPW:

```bash
python scripts/prepare_b59_weather_inputs.py \
  --out-dir data/processed/b59_weather \
  --aux-url 'https://archive-api.open-meteo.com/v1/archive?...2020...' \
  --tail-url 'https://archive-api.open-meteo.com/v1/archive?...2021-01-01...' \
  --requested-latitude 37.876 \
  --requested-longitude -122.249
```

```bash
python scripts/build_b59_2020_epw.py \
  --manifest-out data/processed/b59_weather/b59_2020_epw_manifest.json
```

Both scripts are offline-only. They read saved responses and telemetry and
never fetch or silently fill weather data.
