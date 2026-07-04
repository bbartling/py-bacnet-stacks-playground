# Open-FDD BACnet → Feather concept

**Vibe Code App 16** lab: one process runs a **BACnet/IP mini-device**, a **value updater**, a **poller**, and an **atomic Feather writer**. A second process **tails** completed `.feather` files and prints rows.

Same rusty-bacnet stack as [openfdd-bacnet-mimic](../openfdd-bacnet-mimic/) (YABE / Workbench proven). Default mini-device listens on **UDP 47809** so Open-FDD / OT can keep **47808**.

## Layout

```text
openfdd-bacnet-feather-concept/
  src/bin/bacnet_app.rs      # terminal 1: mini-device + updater + poller/writer
  src/bin/feather_tail.rs    # terminal 2: print new .feather rows
  src/mini_device.rs         # BACnet/IP server (AI:1 demo temp)
  src/poller.rs              # ReadProperty every N seconds
  src/feather_store.rs       # atomic .tmp → .feather (Arrow IPC)
  src/app_config.rs          # TOML config (ports, optional device 5007)
  config/default.toml
  config/field-5007.example.toml
```

## Prerequisites

```bash
# rusty-bacnet beside the playground (same as mimic)
git clone https://github.com/jscott3201/rusty-bacnet.git ~/rusty-bacnet

cd vibe_code_apps_16/openfdd-bacnet-feather-concept
```

Path in `Cargo.toml`: `../../../rusty-bacnet` → `/home/ben/rusty-bacnet` when the playground is `/home/ben/py-bacnet-stacks-playground`.

## Run (two terminals)

```bash
# Terminal 1 — BACnet + Feather writer
./scripts/run_writer.sh
# or: cargo run --bin bacnet_app

# Terminal 2 — Feather tail printer
./scripts/run_tail.sh
# or: cargo run --bin feather_tail
```

### Mental model

```text
Terminal 1: bacnet_app
  ├── mini BACnet server (default :47809, device 599998)
  ├── fake temp updates every 2 seconds (AI:1)
  ├── BACnet poller reads points every 10 seconds
  └── writes completed Feather files atomically

Terminal 2: feather_tail
  └── watches data/feather_store/ and prints new rows
```

Safety: writer only renames `.tmp` → `.feather` after `FileWriter::finish()`. Tailer ignores `.tmp`.

## TOML config

Default: `config/default.toml` (override with `OPENFDD_FEATHER_CONCEPT_CONFIG`).

| Section | Purpose |
|---------|---------|
| `[server]` | Mini-device instance, **UDP port**, NIC, update interval |
| `[poller]` | Poll interval, bind/broadcast |
| `[[poller.points]]` | Points to ReadProperty (local and/or field) |

**Different UDP port (YABE):** set `server.port = 47809` (default). Discover device **599998** from another PC on the LAN — same pattern as the mimic on 47808.

### Bonus: field device 5007 (real temp sensor)

```bash
# Edit host / object_instance to match your controller, then:
OPENFDD_FEATHER_CONCEPT_CONFIG=config/field-5007.example.toml cargo run --bin bacnet_app
```

Example point block:

```toml
[[poller.points]]
enabled = true
device_instance = 5007
object_type = "analog-input"   # or analog-value
object_instance = 1
point_name = "field-temp"
units = "°F"
host = "192.168.204.14"        # controller IP
port = 47808
```

Poller runs Who-Is once at startup for field points, then ReadProperty each cycle.

## Env

| Variable | Meaning |
|----------|---------|
| `OPENFDD_FEATHER_CONCEPT_CONFIG` | Path to TOML |
| `OPENFDD_BACNET_NIC` | NIC for auto IP (default `enp3s0`) |

## Related

| App | Role |
|-----|------|
| [openfdd-bacnet-mimic](../openfdd-bacnet-mimic/) | Device **599999** diagnostic points (Open-FDD parity) |
| Open-FDD edge | Production poll → `feather_store` (this lab is the teaching model) |
