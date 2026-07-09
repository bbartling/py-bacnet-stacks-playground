# Rust + DataFusion parity benchmark

**Machine:** Windows 10, local dev (2026-07-09)  
**Dataset:** BUILDING_100 real client CSV (`HVAC_DATA_ROOT`, 553 MB, 48 equipment, 1.5M rows)

## End-to-end timing (release build)

| Stage | Time | Notes |
| --- | ---: | --- |
| validate | 25 ms | 48 equipment, 300s poll |
| csv_scan (sample) | 1 ms | header + timestamp health |
| ingest → Parquet | 3,219 ms | 1,515,696 rows |
| SQL rules (8) | 245 ms | 6 ok, 2 blocked → **8 ok after SQL fix** |

## Rule results (BUILDING_100)

| Rule | Status | Notes |
| --- | --- | --- |
| FAN-RUNTIME-HOURS | ✅ | `supply_fan` → `fan_cmd` |
| VAV-1 | ✅ | `zone_temp` → `zone_t` |
| AVG-ZONE-TEMP | ✅ | |
| ZONE-COMFORT-PCT | ✅ | |
| FAULT-ELAPSED-HOURS | ✅ | zone comfort proxy |
| ECON-2 | ✅ | `oa_t` + `oa_damper_pct` |
| OAT-METEO | ✅ | hard-range proxy (wx_oa_t join next PR) |
| FC13-SAT-HIGH | ✅ | 55°F ref (no `sat_sp` on site yet) |

## Python validation

```text
python validate_data.py → GO (after poll_seconds wired)
102 pytest passed, 1 skipped
cargo test --workspace → 9 passed
```

## Parity vs pandas oracle

**Partial** — SQL rules execute on real Parquet with logical role columns. Full numeric parity (`fdd_cli compare`) deferred until oracle JSON export per rule is wired. Column mapping fix (`col` + `point_role` headers) was required for BUILDING_100.

## Inventory

| Category | Count |
| --- | ---: |
| Python cookbook rules | 50 |
| SQL rules ported | 8 |
| SQL rules passing on BUILDING_100 | 8 |

## Commands

```bash
cd rust_fdd_core
cargo run -p fdd_cli --release -- benchmark \
  --data-root $HVAC_DATA_ROOT --building BUILDING_100 \
  --parquet-out ../.cache/parquet \
  --rules-dir ../sql_rules \
  --rule-out ../.cache/rule_results \
  --report ../vibe19_agent_spec/benchmarks/RUST_DATAFUSION_PARITY_BENCHMARK.md
```

## Next steps

1. Export pandas fault hours JSON → `fdd_cli compare` per rule
2. Join weather `wx_oa_t` for true OAT-METEO parity
3. Map `sat_sp` when present in `columns.csv`
