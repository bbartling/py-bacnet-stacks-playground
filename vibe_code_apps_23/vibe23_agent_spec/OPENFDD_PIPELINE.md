# Vibe 23 → Open-FDD evidence adapter

This adapter lets the Building 59 telemetry support Open-FDD historian/FDD
analytics during calibration discovery. It is not an EnergyPlus model builder,
not an automated Brick/Haystack mapper, and not a utility-billing or DSM
settlement path.

The reviewed compatibility target is `bbartling/open-fdd` commit
`83a93de38fb9dda3a4545644bcb9b950c145c2d4`, recorded in
`config/openfdd_pin.json`. Later upgrades require a new compatibility run and
pin update; the pin itself is not evidence that Building 59 analytics ran.

## Why this is deliberately strict

Building 59's real point inventory has to be inspected before point mapping.
The adapter exports only CSV columns that have an explicit engineer-reviewed
binding. It rejects missing columns, duplicate point/source bindings, invalid
timestamps, duplicate timestamps after UTC normalization, undeclared source
timezones, and null values unless the mapping explicitly records permission to
retain them. It never fills/resamples data or converts units.

The generated ZIP follows the current public Open-FDD package contract:

```text
LBNL_B59/
  manifest.json                         # openfdd_package_v1, timezone UTC
  VIBE23_OPENFDD_ADAPTER.json           # Vibe 23 provenance extension
  RTU_1/
    history_wide.csv                    # timestamp_utc + original bound columns
    history_wide.json                   # equipType and Haystack point map
```

`VIBE23_OPENFDD_ADAPTER.json` is an explicitly versioned companion document;
Open-FDD readers consume the normal package manifest and sidecars. It retains
the original mapping hash, DOI, acquisition manifest hash, raw source hash,
timestamp interpretation, units, evidence statements, output hash, and a list
of transformations that were intentionally not performed.

## Mapping authoring sequence

1. Run Vibe 23 inventory on the downloaded raw dataset and preserve its
   acquisition manifest/hash.
2. Review the data-description workbook, README, and source columns together.
3. Create a local, source-controlled JSON document with schema
   `vibe23_openfdd_mapping_v1`. Every point must provide `source_column`,
   `haystack_point`, `units`, and a specific evidence statement. Do not infer
   names from filename/header patterns.
4. Begin with one operational system (for example a positively identified RTU
   with fan status, SAT, OAT, MAT/RAT, and verified compressor proof). Run
   Open-FDD only on roles actually supported by the mapped source.
5. Compare schedules, runtime, zone temperatures, cooling operation and load
   shape with the EnergyPlus calibration evidence ledger. Missing roles should
   remain `SKIPPED_MISSING_ROLES`, not become synthetic telemetry.

Example mapping shape (illustrative names only; not a Building 59 assertion):

```json
{
  "schema_version": "vibe23_openfdd_mapping_v1",
  "building_id": "LBNL_B59",
  "grid_minutes": 5,
  "dataset_doi": "10.7941/D1N33Q",
  "acquisition_manifest_sha256": "<64 lowercase hex characters>",
  "mapping_evidence": "Inventory reviewed on YYYY-MM-DD.",
  "equipment": [{
    "equipment_id": "RTU_1",
    "equip_type": "ahu",
    "source_file": "relative/path/to/verified.csv",
    "timestamp_column": "verified_timestamp_column",
    "source_timezone": "America/Los_Angeles",
    "points": [{
      "haystack_point": "fan-status",
      "source_column": "verified_source_header",
      "units": "bool",
      "evidence": "Workbook sheet/row and metadata reference."
    }]
  }]
}
```

## Build and consume

The CLI and Python API are implemented. The checked-in mapping is deliberately
only a placeholder template; a real export still requires reviewed source
bindings:

```bash
cp config/examples/openfdd_mapping.template.json config/b59_openfdd_mapping.json
# Replace every placeholder and the acquisition hash before running:
vibe23 export-openfdd \
  --mapping config/b59_openfdd_mapping.json \
  --raw-root data/raw/building_59 \
  --out data/processed/LBNL_B59_openfdd.zip \
  --report reports/openfdd/adapter_report.json
```

Then import the ZIP using the existing Open-FDD package import / Vibe 19
headless path. Do not run the package through an FDD rule that needs a role
until its sidecar explicitly maps that role. Use the FDD export as one evidence
stream for EnergyPlus schedules, fan runtime, economizer/RTU state, zone
conditions, and end-use plausibility—never as a substitute for calibration
metrics or a reason to call the model calibrated.
