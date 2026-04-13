# Vibe Code App 9 — VOLTTRON Central + TimescaleDB + Forward Historian (ZMQ)

**Companion to App 8 in layout and intent, different topology:** App 8 is an **edge-first** BACnet dashboard on a Pi. App 9 is a **small multi-platform lab**: an **Ubuntu server** runs **VOLTTRON** with **SQLHistorian → TimescaleDB** and **VOLTTRON Central** (no custom web agent like App 8). A **boss Pi** (or any edge collector) runs **Platform Driver** (or bench devices) plus **Forward Historian** so **device topics** land on the central bus and are persisted.

## What ships here

| Path | Purpose |
|------|--------|
| **`docs/volttron-central-forward-timescale-tutorial.md`** | End-to-end bootstrap: Ubuntu + VOLTTRON 9.x (ZMQ), Docker TimescaleDB, auth for Forward Historian, Pi forwarder, verification + troubleshooting. |
| **`examples/central/`** | Example **SQLHistorian** config (`timescale_dialect`), optional env hints. |
| **`examples/edge/`** | Example **Forward Historian** JSON (ZMQ `destination-vip` + `destination-serverkey`). |
| **`docker/docker-compose.timescale.yml`** | Local **TimescaleDB** on the central host (binds to loopback by default). |

## Official docs (read alongside this tutorial)

- [Multi-Platform Connection](https://volttron.readthedocs.io/en/main/deploying-volttron/multi-platform/index.html) — overview of ZMQ vs RabbitMQ paths (this repo uses **ZMQ only**).
- [Forward Historian deployment (ZMQ)](https://volttron.readthedocs.io/en/main/deploying-volttron/multi-platform/forward-historian-deployment.html) — `destination-vip`, `destination-serverkey`, `vctl auth add` on the **destination**.
- [ForwardHistorian configuration](https://volttron.readthedocs.io/en/main/volttron-api/services/ForwardHistorian/README.html) — all forwarder options.
- [SQLHistorian / TimescaleDB](https://volttron.readthedocs.io/en/main/volttron-api/services/SQLHistorian/README.html) — `postgresql` + `timescale_dialect: true`.
- [VolttronCentralPlatform](https://volttron.readthedocs.io/en/main/volttron-api/services/VolttronCentralPlatform/modules.html) and [VolttronCentral](https://volttron.readthedocs.io/en/main/volttron-api/services/VolttronCentral/modules.html) — Central UI stack.
- [VIP Authentication](https://volttron.readthedocs.io/en/main/platform-features/message-bus/vip/vip-authentication.html) — CurveMQ keys behind `vctl auth`.

## Edge reference

For **boss Pi** BACnet + Platform Driver setup, reuse **`vibe_code_apps_7`** / **`vibe_code_apps_8`** tutorials; App 9 only adds the **forward path** and **central** roles.
