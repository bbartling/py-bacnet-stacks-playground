---
name: trend-data
description: >-
  Use when implementing trend collection, time-series storage (Timescale or
  abstraction), charting, CSV export, retention, or per-point sampling
  configuration. Triggers on: trend, Timescale, telemetry, historian, chart,
  COV, sample interval, quality.
---

# Trend data

## Spec anchors

- **`bas_build_spec/spec.md`** — Trends, TrendSample, long-term retention intent.
- **`bas_build_spec/acceptance_criteria.md`** — Trends section.

## Architecture

- Keep ingestion and query behind a **time-series interface** so the TSDB can change without rewriting the API surface.
- Samples: timestamp, value, quality/status; configurable interval per point where required.

## Related skills

- `bacnet-point-modeling` — which points are trended from the field.
- `alarm-workflows` — trend-assisted diagnosis.
- `web-app-bas` — API + UI wiring.
