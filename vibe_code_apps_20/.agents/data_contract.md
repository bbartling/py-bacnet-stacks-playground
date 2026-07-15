# Data contract — OpenFDD WattLab

## BuildingProfile

Geometry/climate intent + `energyplus` block (`prototype_idf`, `epw`, calibration, baseline patch).

## EvidenceRecord

OpenFDD / vibe19-shaped finding with confidence and metrics.

## MeasureBrief

Human-reviewable baseline/proposed changes plus `idf_patch` name/params.

## ResultRecord

`run_id`, `measure_id`, `input_hash` (IDF SHA-256), `status`, `annual`, `quality_flags`, `artifacts`.

## Evidence classes

`measured` · `documented` · `inferred` · `default` · `unknown` · `openfdd_rule`
