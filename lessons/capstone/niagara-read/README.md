# Day 54 — Haystack capstone lives here

The polished **niagara-read** / **`nhaystack-smoke`** tutorial is maintained in vibe code app 17:

**→ [nhaystack-niagara-pi-tutorial](../../../vibe_code_apps_17/nhaystack-niagara-pi-tutorial/)**

## Why not duplicate?

That folder already includes:

- `clap` CLI (`--about`, `--filter`, `--auth basic|scram`, `--probe-scram`)
- Golden fixture capture scripts
- N4.15 station docs + `env.example`
- Wireshark / curl smoke scripts

## Quick start

```bash
cd ../../../vibe_code_apps_17/nhaystack-niagara-pi-tutorial
cp env.example .env    # edit HAYSTACK_PASS
cargo run -- --about
cargo run -- --filter 'point and temp'
./scripts/04_probe_scram_vs_basic.sh
```

## Lesson

[Day 54](../../day54.md) · [Capstone README](../README.md)
