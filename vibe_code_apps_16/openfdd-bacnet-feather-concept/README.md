# openfdd-bacnet-feather-concept

**Enhanced [openfdd-bacnet-mimic](../openfdd-bacnet-mimic/)** — Workbench-friendly BIP server + field poll → Feather + Open-Meteo weather AVs + app-fault BI.

| Piece | Value |
|-------|--------|
| Device name | `openfdd-bacnet-feather-concept` |
| Device instance | **5000** |
| UDP port | **47808** (server **only**) |
| Weather | **AV:1–4** Open-Meteo outdoor T / RH / wind / dewpoint + **CSV:5** location label (Madison WI, every 20 min) |
| Status point | **BI:1** `APP-FAULT` (**active = FAULT**, inactive = OK) |
| Field poll | Multi-device scheduler (VOLTTRON-inspired): **BENS-BENCH** (5007) + **BensFakeAhu** (Pi) |
| Config | [`config/config.toml`](./config/config.toml) |

## Run (Rust)

```bash
cd vibe_code_apps_16/openfdd-bacnet-feather-concept
pkill -f openfdd-bacnet-mimic || true

# Terminal 1 — server + poller + Feather writer
cargo run --release --bin bacnet_app

# Terminal 2 — BACnet probe + new Feather rows
cargo run --release --bin feather_tail
```

## BAS auto-scan → per-device driver files

`bas_scan` (Who-Is + object-list) writes **one TOML per device** — no more scrolling through a 600-line monolith.

| Path | Role |
|------|------|
| [`config/config.toml`](./config/config.toml) | App settings (server, weather, poller scheduler) |
| [`config/drivers/settings.toml`](./config/drivers/settings.toml) | Scan metadata only (not polled) |
| [`config/drivers/devices/*.toml`](./config/drivers/devices/) | **One file per device** — delete file = exclude from polling |
| [`config/drivers/catalog.md`](./config/drivers/catalog.md) | Tables + monolithic TOML for ChatGPT / agents |

Example device file: `config/drivers/devices/5007-bens-benchestest-box.toml`

```toml
name = "BENS-BENCHTEST-BOX"
device_instance = 5007
host = "192.168.204.200"
# ...

[[points]]
point_name = "DUCT-T"
object_type = "analog-input"
object_instance = 1192
```

```bash
# Best results: stop bacnet_app so the scanner can bind UDP 47808 (broadcast I-Am)
pkill -f 'target/release/bacnet_app' || true
cargo run --release --bin bas_scan -- --low 1 --high 4194302 --on-bac0 --merge

# Trim: delete unwanted device files, or set enabled = false on device/points
# Then start polling:
cargo run --release --bin bacnet_app
```

**Edit options:**

- **Recommended:** edit or delete files under `config/drivers/devices/`
- **Catalog apply:** edit monolithic TOML in `catalog.md` and run:

```bash
cargo run --release --bin bas_scan -- --apply-catalog config/drivers/catalog.md
```

`--merge` keeps prior `enabled=false` / `critical` / renames across re-scans. Legacy `config/drivers.toml` is auto-migrated into `devices/` on first load.

## Multi-device poller (VOLTTRON-inspired)

Each `[[poller.devices]]` entry is a driver (see [volttron-platform-driver](https://github.com/eclipse-volttron/volttron-platform-driver)):

| Idea | This app |
|------|----------|
| Per-driver scrape interval | `interval_secs` on each device |
| Phase offset (spread load) | `offset_secs` so devices don't all scrape on the same second |
| Scheduler tick | `tick_ms` — wake, pick overdue devices (most overdue first) |
| Concurrency limit | `max_concurrent` devices scraping in parallel |
| Last-ok tracking | per-device `last_ok` / consecutive failures → **APP-FAULT** for `critical` devices |
| Publish unit | one Feather append per device scrape (all points for that device) |

### BENS-BENCH (device 5007, routed MSTP, `critical=true`)

| Name | Object | Units |
|------|--------|-------|
| OA-H | AI:1168 | %RH |
| OA-T | AI:1173 | °F |
| DUCT-T | AI:1192 | °F → also mirrors to **AV:1** |
| DUCT-P | AI:9334 | in/wc |
| STAT ZN-T | AI:10014 | °F |
| ACTUATOR-POS | AI:10044 | % |
| ACTUATOR-0 | AO:2466 | % |

### BensFakeAhu (device 3456789 @ `192.168.204.13:47808`, BIP direct, `offset_secs=5`)

bacpypes3 fake AHU on Raspberry Pi — all points except `device` and `networkPort`:

| Name | Object | Units |
|------|--------|-------|
| DAP-P … ELEC-PWR | AI:1–7 | in/wc, °F, cfm, kW |
| SF-O … DPR-O | AO:1–4 | % |
| DAP-SP, SAT-SP, OAT-NETWORK | AV:1–3 | in/wc, °F |
| SF-S | BI:1 | bool (1=Active) |
| SF-C | BO:1 | bool |
| Occ-Schedule | MSV:1 | state |

## Outdoor weather (Open-Meteo)

Polled every `weather.interval_secs` (default **1200** = 20 min). First fetch runs immediately at startup; on API failure the configured fallbacks are written to the AVs.

| Point | Object | Source |
|-------|--------|--------|
| `OA-WEATHER-T` | AV:2 | Dry-bulb °F |
| `OA-WEATHER-RH` | AV:3 | Relative humidity % |
| `OA-WEATHER-WIND` | AV:4 | Wind mph |
| `OA-WEATHER-DP` | AV:5 | Dewpoint °F (Magnus from T+RH when not used from API) |

Default city: **Madison Wisconsin** (`weather.city`).

`feather_tail` validates by reading **`OA-WEATHER-T`** present-value over BACnet.

## APP-FAULT (BI:1)

| Present value | Meaning |
|---------------|---------|
| **active / FAULT** | Any field read failed, Feather write failed, DUCT-T missing, data stale (>3 poll intervals), or poller task died |
| **inactive / OK** | Full poll cycle succeeded (all points + Feather append) |

If the poller task crashes, the mini-device **stays up** with `APP-FAULT=FAULT` so Workbench still sees the fault bit (a full process crash takes the whole device offline — that is visible as device loss, not a BI).

## Download Feather → pandas (Windows or Linux)

After `bacnet_app` has been running, copy the single telemetry file:

```text
data/feather_store/telemetry.feather
```

```bash
pip install -r requirements-pandas.txt
python scripts/read_feather_store.py --store C:\Users\you\Downloads\telemetry.feather
python scripts/read_feather_store.py --store C:\Users\you\Downloads\telemetry.feather --csv duct_t.csv
```

```python
from pathlib import Path
import pandas as pd

path = Path(r"C:\Users\you\Downloads\telemetry.feather")
df = pd.read_feather(path)
df["ts_utc"] = pd.to_datetime(df["ts_utc"], utc=True)
df = df.sort_values("ts_utc")
print(df.head())
```

Columns: `ts_utc`, `device_name`, `device_instance`, `object_type`, `object_instance`, `point_name`, `present_value`, `units`.

```bash
# Action-ready latest values (one row per device×point)
python scripts/read_feather_store.py --latest --by-device

# Wide pivot for rules: index=device_name, columns=point_name
python scripts/read_feather_store.py --wide --csv action_ready.csv
```

## Feather store data model

**Not one file per sensor.** Every row is **timestamped**.

### This vibe-code concept app

| Piece | What it is |
| --- | --- |
| **File** | Single `data/feather_store/telemetry.feather` |
| **Per poll** | New rows **appended** (read → concat → atomic rewrite via `.tmp`) |
| **Timestamp** | Yes — column `ts_utc` on every row |
| **Sensors** | **One row per point** with `device_name` — all devices in the same file |
| **Pandas** | `python scripts/read_feather_store.py --by-device --latest` or `--wide` |

Arrow IPC / Feather is not an in-place append format, so each poll rewrites the whole file atomically (`telemetry.feather.tmp` → rename). Readers only open the completed `.feather` (never `.tmp`).

### Open-FDD (full product) — current behavior

Open-FDD **does** write **one shard file per poll cycle** today (not one file per sensor, but still one new file per poll):

| Piece | What it is |
| --- | --- |
| **Per poll / shard** | `write_wide_shard` → `shard-<epoch_ms>-<id>.feather` (**one file per cycle**) |
| **Timestamp** | Yes — column `timestamp` on every row |
| **Sensors** | **Columns** on a **wide** row (`oa_t`, `oa_h`, duct temp slug, …), not separate files |
| **Layout** | `workspace/data/feather_store/<source>/<site_id>/shard-*.feather` |
| **Also** | Historian pivot (`telemetry_pivot.jsonl` / `.arrow`) is a separate long/wide SQL path |

Source of truth in product code: `edge/src/historian/feather_store.rs` (`write_wide_shard` + `shard_name()`). Modbus and BACnet drivers call it once per successful poll batch.

So:

- **Open-FDD:** many small shard files (one wide row each), under `source/site_id/` — **not** one file per sensor, but **yes** one file per poll.
- **This concept app:** one growing `telemetry.feather` (long format, many rows) — intentional lab improvement over the product’s per-poll shards.

A production follow-up for Open-FDD would be append/rotate into fewer files (same idea as this concept), or a true append format (Parquet dataset, Arrow stream, SQLite).

## Config

| File | Role |
|------|------|
| `config/config.toml` | Live lab defaults (tracked) |
| `config/config.example.toml` | Template for a new site |
| `config/config.local.toml` | Optional private override (**gitignored**) |

```bash
# Use a local override:
set OPENFDD_FEATHER_CONCEPT_CONFIG=config/config.local.toml   # Windows
export OPENFDD_FEATHER_CONCEPT_CONFIG=config/config.local.toml # Linux
```

## Architecture

```text
UDP :47808  ← mini-device ONLY (Workbench Who-Is + object-list)
UDP :ephemeral ← poller (routed ReadProperty to field 5007)

Field devices (staggered scrapes):
  BENS-BENCH  5007 @ .200 routed MSTP   interval=10s offset=0  critical
  BensFakeAhu 3456789 @ .13 BIP direct  interval=10s offset=5s
Weather: AV:1–4 OA-WEATHER-* (Open-Meteo every 20 min)
Fault: BI:1 APP-FAULT (active=FAULT / inactive=OK) ← critical devices only
Store: data/feather_store/telemetry.feather  (Arrow IPC / Feather, append)
```

## Workbench

| Field | Expect |
|-------|--------|
| Name | `openfdd-bacnet-feather-concept` |
| Device ID | **device:5000** |
| MAC | `192.168.204.55:0xBAC0` |
| Point | `OA-WEATHER-T` (AV:1) — outdoor dry-bulb from Open-Meteo |
| Point | `APP-FAULT` — **OK** when polls healthy, **FAULT** when not |
