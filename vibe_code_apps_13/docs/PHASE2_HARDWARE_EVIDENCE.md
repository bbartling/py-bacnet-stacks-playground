# Phase 2 — Hardware evidence manifest (`af4e886`)

**rusty-bacnet pin (frozen):** `af4e88680c51eb4da64dac47f0540a35bf184732`  
**Baud / topology:** 38,400; BASRT MAC 0 + JCI FEC MAC 7 + Waveshare USB TO RS485 (C) MAC 3 at physical endpoint.  
**Supervisory trunk validation:** [`scripts/check_mstp_haystack_trunk.sh`](../scripts/check_mstp_haystack_trunk.sh) (Gate 4b) — use for online/offline trunk checks during soak and unplug gates.

Historical captures (`19d205d`, `e3b9edb`, `6a70b85`, `bbartling` fork) are **not** evidence for this pin.

## Gates 2–4 + 4b (committed, 2026-08-31 smoke)

| Gate | Result | Artifact | rusty_bacnet_rev in artifact |
|------|--------|----------|-------------------------------|
| 2 — passive sniff 60s | PASS | [`captures/mstp-passive-af4e886-60s.json`](../captures/mstp-passive-af4e886-60s.json) | yes |
| 3 — FEC client RP AI:1173 | PASS | [`captures/mstp-fec-ai1173-af4e886-oneshot.json`](../captures/mstp-fec-ai1173-af4e886-oneshot.json) | yes |
| 4 — mini-device server | PASS | [`captures/mstp-mini-device-af4e886.log`](../captures/mstp-mini-device-af4e886.log) | log line |
| 4b — Haystack trunk | PASS | [`captures/haystack-trunk/`](../captures/haystack-trunk/) | N/A (supervisory) |

**Serial path (all gates):** `/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_BH001FQ0-if00-port0`

### Gate 2 pass criteria met

- `ok=true`, `rx_bytes>0`, `tokens>0`, sources `0` and `7`, `token_0_from_7>0`, no Rust TX

### Gate 4b Haystack modes

| Mode | When to use |
|------|-------------|
| `check` | Mini-device running — FEC + Rust points `curStatus` ok |
| `fec-only` | FEC/trunk online without requiring Rust mini-device |
| `mini-offline` | After unplug or stop — FEC must stay ok; Rust points absent/down |
| `perturb-stop-mini` | Mini-device stopped deliberately; FEC must stay ok |
| `restore` | Same as `check` after mini-device restarted |

## Endurance / fault gates (run via scripts)

| Gate | Script | Status |
|------|--------|--------|
| Linux timing baseline | **PASS** (post-fix; PR timing evidence closeout) | [`captures/linux-timing-af4e886-20260901T201201Z/`](../captures/linux-timing-af4e886-20260901T201201Z/) |
| Linux timing (prior) | **PARTIAL** — loaded invalid | [`captures/linux-timing-af4e886-20260901T134454Z/`](../captures/linux-timing-af4e886-20260901T134454Z/) (`ERRATA.md`) |
| 24h mini-device continuity | **PASS** (PID 646770 unchanged, etimes>86400) | [`captures/mini-device-24h-continuity-20260901T200935Z.txt`](../captures/mini-device-24h-continuity-20260901T200935Z.txt) |
| 1h mini-device soak | [`scripts/run_mstp_mini_soak.sh`](../scripts/run_mstp_mini_soak.sh) | see `captures/mstp-soak-af4e886-*` |
| USB unplug | [`scripts/run_mstp_usb_unplug_gate.sh`](../scripts/run_mstp_usb_unplug_gate.sh) | **DEFERRED** — operator gate |

## Out of scope for this trunk

- `mstp-probe --profile gate` with ≥500 reads (requires two-adapter C+C topology, not single-port BASRT/FEC trunk)
- shared client+server endpoint, FEC mirror, router, extended frames

## Artifact metadata template

Every new capture directory should include a `manifest.json` with:

- `project_git_sha`, `rusty_bacnet_rev`, `kernel`, `arch`
- `serial_by_id`, `baud`, `ftdi_latency_timer` (if present)
- `topology`, `termination_note`
- `started_utc`, `ended_utc`, `exit_reason`
- `haystack_checks` (count pass/fail) when supervisory validation ran
