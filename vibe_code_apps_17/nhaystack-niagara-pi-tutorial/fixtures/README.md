# Golden fixtures — capture before Workbench license expires

While the live **Niagara 4.15** station is still reachable, run:

```bash
cd nhaystack-niagara-pi-tutorial
source .env
./scripts/03_capture_golden_fixtures.sh
```

Output lands in **`fixtures/golden/`** (gitignored except this README). Use those files to:

1. Regression-test client changes (curl, Rust, rusty-haystack, Open-FDD)
2. Build a future **`niagara-nhaystack-fixture`** HTTP server in vibe code app 17 (no Tridium required)

## Expected files after capture

| File | Source |
|------|--------|
| `about.zinc` | `GET /haystack/about` (Basic auth) |
| `about.headers.txt` | Response headers only |
| `ops.zinc` | `GET /haystack/ops` |
| `read_point_and_cur.csv` | `GET /read?filter=point and cur` |
| `scram_hello.headers.txt` | `GET /about` with `Authorization: HELLO …` (expect no SCRAM challenge) |
| `manifest.json` | Station metadata + capture timestamp |

## Committed examples (no secrets)

Sanitized samples from the lab live in [`example/`](example/) — safe to commit for docs and offline parsing tests.

## Future: nHaystack API double (not implemented yet)

Planned in vibe code app 17 — **not** in upstream rusty-haystack:

```text
Axum HTTP façade  →  serves golden/ or BACnet-backed values
  /haystack/about   →  fixture about.zinc
  /haystack/read    →  fixture CSV or live rusty-bacnet 5007
  HTTP Basic auth   →  same as Niagara HTTPBasicScheme
```

See [FIXTURES_AND_SIM.md](../FIXTURES_AND_SIM.md).
