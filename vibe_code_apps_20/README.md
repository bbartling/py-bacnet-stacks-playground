# OpenFDD WattLab Studio

**WattLab Studio** is the Streamlit cockpit for [OpenFDD WattLab](AGENTS.md) (Vibe App 20): turn a [Vibe 19](../vibe_code_apps_19/) WattLab dump into model, benchmark, ECM, twin, and capital-plan workflows.

Vibe 19 = measured FDD. Vibe 20 = model / ECM / capital. They stay separate apps.

Agent / CLI / package detail lives in [`AGENTS.md`](AGENTS.md) — this README is for running the UI.

## Run (Docker / GHCR)

Multi-arch images publish from `develop` via `.github/workflows/vibe20-ghcr.yml`:

```powershell
docker pull ghcr.io/bbartling/vibe20:latest
docker rm -f vibe20 2>$null
# Use 8520 when vibe19 already owns 8501/8502/8503 on the same host
docker run -d --restart unless-stopped -p 8520:8501 --name vibe20 ghcr.io/bbartling/vibe20:latest
# open http://localhost:8520
```

Tags: `:latest`, `:develop`, `:sha-<commit>`. Real EnergyPlus sims need a host Docker image `energyplus-mcp-dev` (see [`AGENTS.md`](AGENTS.md)) — not inside this container.

## Run (local)

```powershell
cd vibe_code_apps_20
pip install -e ".[studio]"
wattlab studio
# or: streamlit run studio.py --server.port 8520
```

## Studio pages

1. **Ingest** — upload `wattlab_dump_*.zip` from vibe19 Export → summary, gaps, FDD highlights, next-step framing
2. **Data Explorer** — browse dump analytic tables + shared `telemetry/` CSVs (measured evidence)
3. **Assumption Ledger** — read-only provenance (`MEASURED` / `INFERRED` / `DEFAULTED` / `HUMAN` / `MISSING`)
4. **Model** — profile editor, provenance, calibration badge
5. **Benchmark** — bills vs peer bands, shared-meter scenarios, monthly signatures (`campus.json` — any site)
6. **Fuel Weather** — campus bills × Open-Meteo/synthetic HDD/CDD, intensity/demand heatmaps, gas×HDD & elec×CDD R²
7. **Existing Building Hypothesis Lab** — sparse-input scenario ladder + artifact downloads
8. **ECM Easy Buttons** — catalog cards/packages (proxy + conceptual EnergyPlus)
9. **Measures** — catalog + FDD-suggested measures, proxy savings, editable costs
10. **Twin loop** — dry-run plan or Docker EnergyPlus runs, crosscheck verdicts
11. **EP Results** — post-sim charts / scorecards
12. **Capital plan** — payback / ROI / NPV gated by benchmark guardrails (`PUBLISH` / `INVESTIGATE`)

Most pages work dry-run without EnergyPlus. Start on **Ingest** with a dump zip, or **Benchmark / Fuel Weather** with any `campus.json` + bill CSVs (`examples/liberty/` is a practice example only; CI uses the shared-meter fixture).

## Pre-ship smoke (local)

GHCR CI builds/pushes the image only. Before merge, run:

```powershell
python scripts/smoke_studio.py
python -m pytest tests/test_studio_app.py -q
# with Studio on :8520 (host or Docker):
python scripts/browser_smoke_vibe20.py --url http://localhost:8520 --screenshots .artifacts/browser/native
```

## Related docs

| Doc | For |
| --- | --- |
| [`AGENTS.md`](AGENTS.md) | Agent handbook, CLI (`wattlab twin` / `seed` / …), hard rules |
| [`../vibe_code_apps_19/docs/PACKAGE_SPEC.md`](../vibe_code_apps_19/docs/PACKAGE_SPEC.md) | Historian package layout that feeds dumps |
| [`docs/`](docs/) | ECM briefs, units, privacy, benchmarks |
