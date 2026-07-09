# rust_fdd_core

Rust + Apache Arrow + Parquet + DataFusion SQL engine for vibe19 deterministic FDD analytics.

## Build

```bash
cargo build --release
cargo test --workspace
cargo clippy --workspace --all-targets -- -D warnings
```

## CLI

```bash
cargo run -p fdd_cli -- validate --data-root $HVAC_DATA_ROOT --building BUILDING_100
cargo run -p fdd_cli -- ingest --data-root $HVAC_DATA_ROOT --building BUILDING_100 --out ../.cache/parquet
cargo run -p fdd_cli -- run-rules --parquet ../.cache/parquet --rules-dir ../sql_rules
cargo run -p fdd_cli -- benchmark --data-root $HVAC_DATA_ROOT --building BUILDING_100
```

Release binary: `target/release/fdd_cli` (used by Python `rust_fdd_bridge.py` when built).

## Crates

| Crate | Purpose |
| --- | --- |
| `fdd_core` | Models, validation, column role map |
| `fdd_csv` | CSV header scan, timestamp health |
| `fdd_store` | CSV → Parquet sidecars |
| `fdd_sql` | DataFusion queries |
| `fdd_rules` | SQL rule registry runner |
| `fdd_bench` | Benchmark + parity compare |
| `fdd_cli` | Command-line entry point |

Docs: [`../vibe19_agent_spec/docs/RUST_CORE_STAGE1.md`](../vibe19_agent_spec/docs/RUST_CORE_STAGE1.md)
