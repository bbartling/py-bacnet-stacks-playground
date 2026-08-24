# Vibe 23 Data Contract

## Raw source
`data/raw/` is immutable local source material and gitignored.

Expected Dryad release files:
- `Building_59.zip`
- `data_description_table_3year_clean_data.xlsx`
- `metadata_Dryad_Bldg59.docx`
- `README_Dryad_Bldg59.txt`

The full Dryad download may wrap these files in another ZIP. The downloader safely extracts the wrapper, finds exactly one `Building_59.zip`, then safely extracts the nested telemetry archive.

The public endpoint may return HTTP 401/403 to an automated client. Use an authorized `VIBE23_DRYAD_BEARER_TOKEN`, an authorized URL override, or download all four release files manually and pass their directory with `vibe23 download --source-release <DIR>`. The manifest records acquisition mode and hashes, never credentials.

## Derived data
`data/processed/` holds inventory tables, explicit point bindings, aligned measured targets and measured-vs-sim comparison tables. Large derived telemetry remains local.

## Required provenance for a published target
- DOI/acquisition manifest hash;
- exact source file path/hash;
- timestamp column and timezone interpretation;
- value column and units;
- cleaning/gap policy;
- aggregation method;
- output hash.

## Power aggregation
For sampled power in kW, energy is integrated as power × elapsed hours using a left-hold convention. Gaps materially larger than the normal sample interval fail closed rather than being silently integrated. Peak kW is the maximum measured sample in the reporting period.

## Timezone
Do not strip timezone information casually. BAS timestamps, DST, EnergyPlus local standard time, weather timestamps and utility demand intervals must be reconciled explicitly before calibration or tariff scoring.
