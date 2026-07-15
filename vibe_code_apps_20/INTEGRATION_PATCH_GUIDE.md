# Integration Patch Guide

Copy this package into `vibe_code_apps_20`. Then:

1. Add Pydantic/dataclass models matching `schemas/`.
2. Add an artifact store rooted at `.artifacts/<run_id>/`.
3. Make `explore_sketchbox.py` read-only by default.
4. Route all writes through `action_sketchbox.py`.
5. Have `run_measure.py` consume an approved MeasureBrief rather than free-form values.
6. Add `--dry-run`, `--project-id`, `--measure-brief`, and `--artifact-dir` options.
7. Add a redaction layer before DOM or screenshot metadata is persisted.
8. Add unit tests and captured-fixture selector tests.
9. Keep credentials exclusively in environment variables or an approved secret store.
10. Update the App 20 README to link to `AGENTS.md`.
