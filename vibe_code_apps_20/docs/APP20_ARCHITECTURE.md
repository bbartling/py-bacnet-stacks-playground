# Recommended App 20 Architecture

## Existing script boundaries

- `sketchbox_driver.py`: authentication, browser lifecycle, probes, shared primitives.
- `explore_sketchbox.py`: read-only UI discovery and artifact collection.
- `action_sketchbox.py`: deliberate UI writes and verified actions.
- `run_measure.py`: measure application and result workflow.
- `config.py`: environment and non-secret runtime configuration.

Preserve these boundaries.

## Proposed modules

```text
app20/
  domain/
    building_profile.py
    evidence.py
    ecm.py
    measure_brief.py
    results.py
  adapters/
    vibe19.py
    sketchbox_playwright.py
    sketchbox_exports.py
  services/
    candidate_generator.py
    applicability.py
    run_orchestrator.py
    result_qa.py
    portfolio.py
  storage/
    artifact_store.py
    run_manifest.py
```

## State machine

`DISCOVER → AUTHENTICATE → LOAD_OR_CREATE → BASELINE_INPUT → BASELINE_VERIFY → BASELINE_RUN → MEASURE_INPUT → MEASURE_VERIFY → MEASURE_RUN → EXPORT → QA → COMPLETE`

Every transition writes a run-manifest event.

## Idempotency

Each run is keyed by:
- building profile hash
- baseline hash
- measure brief hash
- Sketchbox version/UI fingerprint when observable

The orchestrator must detect completed equivalent runs and avoid duplicate measure creation.
