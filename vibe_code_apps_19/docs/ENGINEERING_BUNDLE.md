# OpenFDD Engineering Bundle (`openfdd_engineering_bundle_v1`)

The Streamlit Export tab writes **one** standard bundle (today’s summary profile).
Diagnostic/forensic per-rule timeseries remain on the CLI:

```bash
python scripts/agent_afdd.py --package BUILDING.zip --out /tmp/bundle --export-profile diagnostic
```

## Schema

| Field | Value |
| --- | --- |
| `schema_version` | `openfdd_engineering_bundle_v1` |
| `legacy_schema_version` | `wattlab_dump_v3` |
| `product` | `OpenFDD Engineering Bundle` |

Downstream React/Rust readers should accept **either** `schema_version` or
`legacy_schema_version == wattlab_dump_v3`. Older `wattlab_dump_v2` zips remain
readable where the application already did.

`package_file_count` is on-disk files after `MANIFEST.json` is written.
`manifest_entry_count` / `file_count` is the index length (directory entries
and aliases can make these differ).

## Provenance

`MANIFEST.json.provenance` includes OpenFDD version, catalog hashes, app git
SHA, source package hash, timezone, and grid. Missing SHAs set
`provenance_incomplete: true` (typical for a PyPI wheel with no git metadata).

## Canonical tables

Prefer `*.parquet` when present. CSV twins are human-facing during migration.
Shared `telemetry/` + `fault_intervals.json` replace a full timeseries per rule.

## EnergyPlus

`model_seed.json` is operational evidence, not a calibrated model. Read
`calibration_readiness.json` before treating UTC historian hours as local
EnergyPlus schedules.
