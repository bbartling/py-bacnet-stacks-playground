# openfdd-bacnet-feather-concept

**Enhanced [openfdd-bacnet-mimic](../openfdd-bacnet-mimic/)** — Workbench-friendly BIP server + field poll → Feather → clone AV.

| Piece | Value |
|-------|--------|
| Device name | `openfdd-bacnet-feather-concept` |
| Device instance | **5000** |
| UDP port | **47808** (server **only**) |
| Clone point | **AV:1** `5007-duct-t-clone` (**°F**, BACnet units=64) |
| Field poll | **5007** AI:1192 DUCT-T (routed MSTP) → Feather every 10s |
| Config | [`config/config.toml`](./config/config.toml) |

## Run (Rust)

```bash
cd vibe_code_apps_16/openfdd-bacnet-feather-concept
pkill -f openfdd-bacnet-mimic || true

# Terminal 1 — server + poller + Feather writer
cargo run --release --bin bacnet_app

# Terminal 2 — BACnet probe + new Feather shards
cargo run --release --bin feather_tail
```

## Download Feather → pandas (Windows or Linux)

After `bacnet_app` has been running, copy the store folder to your PC:

```text
data/feather_store/*.feather
```

On Windows (PowerShell or cmd):

```bash
pip install -r requirements-pandas.txt

# Point --store at the folder you copied
python scripts/read_feather_store.py --store C:\Users\you\Downloads\feather_store

# Optional CSV export for Excel
python scripts/read_feather_store.py --store C:\Users\you\Downloads\feather_store --csv duct_t.csv
```

In a notebook / script:

```python
from pathlib import Path
import pandas as pd

store = Path(r"C:\Users\you\Downloads\feather_store")
df = pd.concat([pd.read_feather(p) for p in sorted(store.glob("*.feather"))], ignore_index=True)
df["ts_utc"] = pd.to_datetime(df["ts_utc"], utc=True)
df = df.sort_values("ts_utc")
print(df.head())
```

Columns: `ts_utc`, `device_instance`, `object_type`, `object_instance`, `point_name`, `present_value`, `units`.

## Feather store data model

**Not one file per sensor.** Each poll writes a **shard** (batch file). Every row is **timestamped**.

### Open-FDD (full product)

| Piece | What it is |
| --- | --- |
| **Per poll / shard** | One (or a few) **wide** rows written each cycle |
| **Timestamp** | Yes — column `timestamp` on every row |
| **Sensors** | **Columns** on that row (`oa_t`, `oa_h`, duct temp slug, …), not separate files |
| **Also** | Historian pivot (`telemetry_pivot.jsonl` / `.arrow`) is a separate long/wide SQL path |

Layout:

```text
workspace/data/feather_store/<source>/<site_id>/shard-<time>-<id>.feather
# e.g. feather_store/modbus/site:local/shard-....feather
```

So: **timestamp + many sensor values in the same row**, shards under **source × site**, not one feather file per point.

### This vibe-code concept app

Slightly different shape (**long** format), but the same ideas:

| Piece | What it is |
| --- | --- |
| **Per poll / shard** | One `shard-*.feather` per poll batch under `data/feather_store/` |
| **Timestamp** | Yes — column `ts_utc` on every row |
| **Sensors** | **One row per point** (`point_name`, `present_value`, …), not one file per sensor |
| **Pandas** | Concatenate all shards → one DataFrame (see script above) |

Still **timestamped**, and **not** one file per sensor — one shard per poll batch.

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

Field: BIP router 192.168.204.200:47808 → MSTP net 2000 MAC 7 → AI:1192 DUCT-T
Clone: AV:1 5007-duct-t-clone (units °F = 64)
Store: data/feather_store/shard-*.feather  (Arrow IPC / Feather)
```

## Workbench

| Field | Expect |
|-------|--------|
| Name | `openfdd-bacnet-feather-concept` |
| Device ID | **device:5000** |
| MAC | `192.168.204.55:0xBAC0` |
| Point | `5007-duct-t-clone` in **°F** (not °C) |
