# Niagara nHaystack fixture server (roadmap)

**Status:** design only — capture golden files first ([`fixtures/`](fixtures/)), implement sim later in **vibe code app 17** or **Open-FDD** bench profile.

## Problem

Tridium Workbench licenses expire. Open-FDD, rusty-haystack, and pyhaystack still need a **Niagara-shaped Haystack HTTP API** for CI and local dev.

## Not a perfect Niagara clone

Target **contract compatibility**, not Workbench fidelity:

| Must match | Can skip |
|------------|----------|
| `https://host/haystack/about` + Zinc grid shape | Station provisioning UI |
| `read?filter=point and cur` CSV/Zinc | NHaystack cache rebuild |
| HTTP Basic (`HTTPBasicScheme`) | DigestScheme browser login |
| Self-signed TLS optional | Haystack SCRAM on nHaystack |
| BACnet point ids (`BacnetNetwork/.../OA~2dT`) | Full nav/history/watch ops (phase 2+) |
| Writable ACTUATOR points (phase 2) | Tridium auth scheme zoo |

## Where it should live

| Project | Role |
|---------|------|
| **vibe_code_apps_17** | Tutorial + golden capture + prototype `niagara-nhaystack-fixture` binary |
| **Open-FDD** | Docker compose profile `bench-nhaystack-fixture` for edge driver tests |
| **rusty-haystack upstream** | Stay spec-pure (SCRAM server, codecs) — no Niagara mimic |

## Three phases

### Phase 1 — Static fixture HTTP server (cheap)

- Serve committed + captured `fixtures/golden/*`
- Basic auth gate matching lab `open_fdd` user
- Enough for Open-FDD `/api/haystack/test` and driver poll

### Phase 2 — BACnet-backed values

- Map Haystack refs → `bacnet:5007:analog-input:*` via rusty-bacnet
- Same subnet bench as [BACnet tutorials](../../README.md)
- Live OA-T / DUCT-T track field sim or device 5007

### Phase 3 — pointWrite

- ACTUATOR-0 / ACTUATOR-POS writable rows from golden CSV
- Record write request/response pairs during golden capture

## Capture checklist (do now on live N4.15 station)

```bash
./scripts/03_capture_golden_fixtures.sh
./scripts/04_probe_scram_vs_basic.sh
cargo run -- --probe-scram
```

Store artifacts under `fixtures/golden/` and back up off-repo before license lapse.
