# Open-FDD BACnet server mimic

Part of **[Vibe Code App 16](../../README.md)** — Rust BACnet stack lab (`py-bacnet-stacks-playground`).

Standalone Rust project: Open-FDD object database (device **599999**, diagnostic AV/BV points) on UDP **47808**.

**Behavior:** answers **Who-Is** with **I-Am**. No periodic I-Am broadcasts (Tridium and other BMS tools send Who-Is when you discover devices).

## Quick start

```bash
cd vibe_code_apps_16/openfdd-bacnet-mimic
# from repo root: cd ~/py-bacnet-stacks-playground/vibe_code_apps_16/openfdd-bacnet-mimic

# Terminal 1 — start server
./scripts/run.sh

# Terminal 2 — probe from this host
./scripts/probe.sh
```

Stop Open-FDD Docker first if it already binds port **47808**.

## Project layout

```text
openfdd-bacnet-mimic/
├── Cargo.toml              # two binaries + shared library
├── README.md
├── scripts/
│   ├── common.sh           # bench IP / broadcast / device id
│   ├── run.sh              # build + start server
│   └── probe.sh            # unicast read + Who-Is test
└── src/
    ├── lib.rs              # crate root
    ├── config.rs           # defaults + clap CLI structs
    ├── network.rs          # NIC detect, UDP bind, broadcast math
    ├── database.rs         # BACnet AV/BV objects (from Open-FDD)
    ├── server.rs           # server logic
    ├── probe.rs            # client probe logic
    └── bin/
        ├── server.rs       # → openfdd-bacnet-mimic
        └── probe.rs        # → bacnet-probe
```

| File | Role |
|------|------|
| `config.rs` | Device **599999**, vendor **999**, CLI flags |
| `database.rs` | Seven BACnet objects (fault count, OA temp, …) |
| `network.rs` | Auto-detect IP on `enp3s0`, bind `0.0.0.0:47808` |
| `server.rs` | `BACnetServer` from rusty-bacnet — listen until Ctrl+C |
| `probe.rs` | Read `object-name`, then global Who-Is |

## Cargo commands

```bash
# Server (same as ./scripts/run.sh)
cargo run --release --bin openfdd-bacnet-mimic -- --replace-existing

# Probe
cargo run --release --bin bacnet-probe -- --bind 192.168.204.55 --device 599999
```

## Environment (optional)

| Variable | Default | Meaning |
|----------|---------|---------|
| `OPENFDD_BACNET_NIC` | `enp3s0` | Interface for auto IP |
| `OPENFDD_BACNET_ADDRESS` | (from NIC) | Host IPv4 in I-Am |
| `OPENFDD_BACNET_BROADCAST` | `x.x.x.255` | Directed broadcast |
| `OPENFDD_BACNET_INSTANCE` | `599999` | Device instance |

## BACnet objects (device 599999)

| Object | Name |
|--------|------|
| analog-value:9003 | openfdd-active-fault-count |
| binary-value:9004 | openfdd-faults-present |
| binary-value:9010 | openfdd-optimization-enabled |
| analog-value:9101 | outside-air-temperature |
| analog-value:9102 | outside-air-humidity |
| analog-value:9103 | outside-air-dewpoint |

## What to expect from probe.sh

| Check | Same host | Tridium / other PC |
|-------|-----------|---------------------|
| Unicast read | **PASS** (`object-name = "OpenFDD"`) | N/A |
| Global Who-Is | Often **0 devices** (rusty-bacnet quirk) | **PASS** — normal discover |

Same-host Who-Is returning zero is a **client library limitation**, not a broken server. Tridium discover from another machine is the real test.

## Dependency

Uses local **rusty-bacnet** (clone to `/home/ben/rusty-bacnet` or adjust paths in `Cargo.toml`):

```text
~/rusty-bacnet/crates/bacnet-{server,client,objects,...}
```

Relative path from this crate: `../../../rusty-bacnet/crates/...`

## Related bench docs

Open-FDD v3.2.5 gaps and v3.2.6 fix list:  
`~/open-fdd/workspace/reports/REV_325_RIGOROUS_TEST_REPORT.md`

## Restore Open-FDD bench

```bash
cd ~/open-fdd
docker start openfdd-bridge openfdd-commission openfdd-caddy openfdd-haystack-gateway
./scripts/openfdd_bacnet_poll_daemon.sh start
```
