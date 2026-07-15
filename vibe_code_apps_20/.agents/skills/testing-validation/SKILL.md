# Skill: testing-validation

Verify OpenFDD WattLab code and Docker path.

## Required

- Unit: schemas, examples, AGENTS keywords, **forbidden legacy brand scrub**
- Integration (Docker): image present, sample sim, Madison easy-button dry-run / live when available

```powershell
cd vibe_code_apps_20
python -m pytest tests -q
python madison_office.py --dry-run
```
