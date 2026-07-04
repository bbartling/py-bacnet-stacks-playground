# Vibe Code App 16 — Rust BACnet stack lab

**Active featured build.** Hands-on [`rusty-bacnet`](https://github.com/jscott3201/rusty-bacnet) server + client work: Open-FDD device mimic, Who-Is / ReadProperty probes, and (planned) Python bindings + BACpypes3 benchmarks.

| Item | Link |
| --- | --- |
| **Open-FDD BACnet mimic** (device 599999) | [openfdd-bacnet-mimic/](./openfdd-bacnet-mimic/) |
| **BACnet → Feather concept** (mini-device + poller + store) | [openfdd-bacnet-feather-concept/](./openfdd-bacnet-feather-concept/) |
| **rusty-bacnet upstream** | [github.com/jscott3201/rusty-bacnet](https://github.com/jscott3201/rusty-bacnet) |
| **BACpypes3 compare baseline** | [JoelBender/BACpypes3](https://github.com/JoelBender/BACpypes3) |
| **Open-FDD bench context** | [REV_325 rigorous report](https://github.com/bbartling/open-fdd) · device 599999 commission-read gaps |

## What lives here (today)

```text
vibe_code_apps_16/
  README.md                    ← this file
  openfdd-bacnet-mimic/
    src/                       lib + server/client layout (read server/main.rs first)
    scripts/run.sh             start server on UDP :47808
    scripts/probe.sh           unicast read + Who-Is test client
  openfdd-bacnet-feather-concept/
    src/bin/bacnet_app.rs      mini-device + poller + Feather writer
    src/bin/feather_tail.rs    print new .feather rows
    config/config.toml         device 5000 on :47808 + field 5007 poll
```

The **mimic** implements Open-FDD diagnostic points on **device instance 599999** — same object model as production `bacnet_server_runtime.rs`. It **answers Who-Is with I-Am** (no periodic broadcasts). Validated with **Tridium Workbench** / **YABE** from the LAN.

The **Feather concept** is the teaching model for Open-FDD poll → historian: one process owns BACnet server + poller + atomic Feather writes; a second process tails the store. See [openfdd-bacnet-feather-concept/README.md](./openfdd-bacnet-feather-concept/README.md#feather-store-data-model) for how shards, timestamps, and sensor columns work (Open-FDD **wide** rows vs this lab’s **long** rows — neither is one file per sensor).

## Quick start — mimic

```bash
# Clone rusty-bacnet beside this repo (or under ~/rusty-bacnet)
git clone https://github.com/jscott3201/rusty-bacnet.git ~/rusty-bacnet

cd vibe_code_apps_16/openfdd-bacnet-mimic

# Terminal 1 — server
./scripts/run.sh

# Terminal 2 — probe (same host: unicast PASS; Who-Is may show 0 — see README)
./scripts/probe.sh
```

## Quick start — Feather concept

```bash
cd vibe_code_apps_16/openfdd-bacnet-feather-concept

# Terminal 1 — BACnet mini-device (:47809) + poller + Feather writer
./scripts/run_writer.sh

# Terminal 2 — print new Feather rows
./scripts/run_tail.sh
```

Optional field device **5007**: see `config/field-5007.example.toml`.

**Prerequisite:** `rusty-bacnet` at `../../../rusty-bacnet` relative to the crate (i.e. `/home/ben/rusty-bacnet` when the playground lives at `/home/ben/py-bacnet-stacks-playground`).

## Roadmap (this checkpoint)

| Track | Status |
| --- | --- |
| Open-FDD mimic server + probe | **Active** — [openfdd-bacnet-mimic](./openfdd-bacnet-mimic/) |
| BACnet → Feather concept (2 binaries) | **Active** — [openfdd-bacnet-feather-concept](./openfdd-bacnet-feather-concept/) |
| rusty-bacnet server lifecycle vs Open-FDD gaps | Documented in Open-FDD REV_325 report |
| Python bindings (PyO3) for client/server smoke tests | Planned |
| BACpypes3 vs rusty-bacnet discover/read benchmarks | Planned |
| MS/TP + embedded path | See [App 15 — Rust embedded BACnet](../vibe_code_apps_15/) |

## Related checkpoints

| # | Project |
| --- | --- |
| 4 | Python BACnet server apps (BACpypes3 baseline) |
| 12 | Edge-to-cloud HVAC FDD pipeline |
| 15 | Rust embedded BACnet on NUCLEO-F401RE (RS-485 / MS/TP lab) |
| 17 | Project Haystack playground |
| 18 | DIY BAS / Haystack data lake |

## Status

**Active** — `openfdd-bacnet-mimic` + `openfdd-bacnet-feather-concept`; more rusty-bacnet experiments land here over time.
