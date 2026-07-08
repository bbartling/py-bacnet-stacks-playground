# bad-rusty-bacnet-app

**Intentionally malformed** BACnet clients for lab study — same anti-patterns in **Rust** and **Python** ([rusty-bacnet](https://github.com/jscott3201/rusty-bacnet)).

Emulates Open-FDD `802258a` failure points from:

`open-fdd/workspace/reports/BACNET_PCAP_802258A_vs_VIBE16_REPORT.md`

Do **not** deploy. Use to compare PCAP signatures against vibe16 (good) and Open-FDD (bad).

---

## Repo layout

```
bad_rusty_bacnet_app/
  config.toml                 # shared bench config (both implementations)
  rust/
    Cargo.toml
    src/main.rs               # bad client — native bacnet-client crate
  python/
    bad_bacnet_app.py         # bad client — pip install rusty-bacnet
    requirements.txt
  scripts/
    run_bad_capture.sh        # --impl rust|python
    analyze_bacnet_pcap.py
    bad_pcap_expectations.toml
  data/pcap/
    rust/                     # Rust capture artifacts
    python/                   # Python capture artifacts
```

---

## What NOT to do (both implementations)

| ID | Anti-pattern | Rust + Python | Open-FDD `802258a` |
|----|--------------|---------------|---------------------|
| **FP-1** | Who-Is `(0..4194303)` before every poll read | Yes | `prepare_device_for_read()` → `run_whois()` |
| **FP-2** | New client per poll cycle | Yes | `build_client()` / `stop_client()` in `bacnet_live.rs` |
| **FP-3** | MSTP routing never persisted | Discarded with client | `merge_missing_field_devices()` drops routing |
| **FP-4** | `read_property_from_device()` for MSTP 5007 | Yes — no routed read | Same |
| **FP-5** | Dual poll loops (bridge + commission) | Yes — offset 5s | Bridge + commission both poll |
| **FP-6** | Who-Is when registry empty | Discovery every cycle | `ensure_field_devices_from_whois()` |

**vibe16** does none of this — one shared client, no Who-Is during poll, `read_property_routed()` from TOML.

### Rust-only note: ephemeral broadcast port

With `port(0)`, rusty-bacnet sends broadcast Who-Is to `192.168.204.255:<ephemeral>` instead of `:47808`. Directed Who-Is / reads still hit `:47808`. Python bindings share the same transport.

---

## Quick start

### Setup (once)

```bash
cd /home/ben/bad_rusty_bacnet_app
python3 -m venv .venv
.venv/bin/pip install -r python/requirements.txt
cd rust && cargo build --release && cd ..
```

### Run bad app

**Rust:**

```bash
./rust/target/release/bad_bacnet_app --config config.toml --duration-secs 90
```

**Python** ([quick-start-python](https://github.com/jscott3201/rusty-bacnet#quick-start-python)):

```bash
.venv/bin/python python/bad_bacnet_app.py --config config.toml --duration-secs 90
```

### PCAP capture + analyze

```bash
./scripts/run_bad_capture.sh --impl rust --duration 90
./scripts/run_bad_capture.sh --impl python --duration 90
```

Bench: `192.168.204.55` on `enp3s0`, router `192.168.204.200` (MSTP 5007), BIP `3456789` @ `.13`, `3456790` @ `.14`.

---

## PCAP results

### Rust (90s, 2026-07-07)

`data/pcap/rust/bad_bacnet_20260707T201943Z.pcap` — 8250 bytes, 90 packets, **FAIL** (intentional)

| Metric | Rust bad app | vibe16 | Open-FDD 802258a |
|--------|--------------|--------|------------------|
| Peak pkt/s | 6 | 10 | 32 |
| Broadcast to `.255` | 18 (wrong port) | 0 | 14 |
| TX to `.13` | 18 (reads OK) | steady | **0** |
| MSTP 5007 | FAIL | OK (routed) | FAIL |

### Python (30s, 2026-07-07)

`data/pcap/python/bad_bacnet_20260707T235246Z.pcap` — 3376 bytes, 44 packets, **WARN**

| Metric | Python bad app |
|--------|----------------|
| Peak pkt/s | 7 |
| ReadProperty (svc 12) | 8 |
| Who-Is / I-Am (svc 8/0) | 16 each |
| TX to `.13` / `.14` | 8 each, req/resp 1.00 |
| TX to `.200` | 8, no RX (router offline) |
| MSTP 5007 | FAIL (no Forwarded-NPDU) |

Same behavioral signature as Rust: BIP reads succeed after directed Who-Is; MSTP 5007 fails every cycle.

---

## Implementation comparison

| | Rust (`rust/`) | Python (`python/`) |
|--|----------------|---------------------|
| Library | `bacnet-client` path dep | `pip install rusty-bacnet` |
| Client lifecycle | `bip_builder().port(0).build()` + `stop()` | `async with BACnetClient(port=0)` |
| Who-Is network | `who_is_network(2000, …)` | not exposed in Python API — uses broadcast + directed |
| Reads | `read_property_from_device()` | `read_property_from_device()` |
| Dual loop | `tokio::spawn` × 2 | `asyncio.create_task` × 2 |

Both read the same `config.toml` and produce comparable PCAP for regression study.

---

## Fix checklist (for Open-FDD, not this repo)

1. One shared client per process — never stop between reads.
2. No Who-Is during steady-state poll; static TOML routing for MSTP.
3. `read_property_routed()` for device 5007.
4. Persist MSTP routing in `driver_tree.json`.
5. Single poll loop, or dedupe bridge vs commission.
6. Fix BVLC broadcast dest port when client uses ephemeral bind.

---

## References

- [rusty-bacnet Python quick start](https://github.com/jscott3201/rusty-bacnet#quick-start-python)
- Open-FDD PCAP report: `open-fdd/workspace/reports/BACNET_PCAP_802258A_vs_VIBE16_REPORT.md`
- vibe16 good pattern: `py-bacnet-stacks-playground/.../openfdd-bacnet-feather-concept/src/poller.rs`
- GitHub: #464 (MSTP routing), #467 (EMFILE / client lifecycle)
