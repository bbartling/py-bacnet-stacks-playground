# Vibe Code App 15 — Rust embedded BACnet device (planned)

**Planned lab.** Embedded BACnet on **STM32** using **Rust** (not bare-metal C): `no_std` / `embedded-hal` path toward **BACnet MS/TP** over **RS-485**, sharing protocol lessons with [App 16](../vibe_code_apps_16/) (`rusty-bacnet` on Linux) and Python MS/TP router work in [App 13](../vibe_code_apps_13/).

## Hardware lab board

| Item | Link |
| --- | --- |
| **NUCLEO-F401RE** (STM32F401RE, Arduino headers, ST-LINK) | [DigiKey — NUCLEO-F401RE](https://www.digikey.com/en/products/detail/stmicroelectronics/NUCLEO-F401RE/4695525) |
| **ST product page** | [NUCLEO-F401RE evaluation board](https://www.st.com/en/evaluation-tools/nucleo-f401re.html) |

Use this board to experiment with:

- UART / RS-485 transceiver wiring (e.g. MAX485 breakout on USART)
- MS/TP token-passing and frame timing at the wire
- Contrasting **embedded Rust** device firmware vs Linux **rusty-bacnet** server in [openfdd-bacnet-mimic](../vibe_code_apps_16/openfdd-bacnet-mimic/)

## Target architecture (draft)

```text
NUCLEO-F401RE + RS-485 transceiver
        │  BACnet MS/TP (or raw UART lab frames first)
        v
Linux bench / Pi  ──►  rusty-bacnet router or MS/TP master (App 13/16)
        │
        v
Open-FDD / Tridium discover & read tests
```

## Planned milestones

1. Blink + UART echo on NUCLEO (Rust `embedded` template).
2. RS-485 half-duplex send/receive loopback with scope / logic analyzer.
3. MS/TP frame encode/decode crate evaluation (Rust-first; avoid shipping new C stack unless required).
4. Minimal BACnet device object (analog-input) on the wire.
5. Integrate with [App 16](../vibe_code_apps_16/) Linux-side discovery/read tests.

## Related checkpoints

| # | Project |
| --- | --- |
| 13 | DIY BACnet router (Pi/Linux MS/TP) |
| 14 | BACnet routing research lab (BACpypes3 pcaps) |
| 16 | Rust BACnet stack lab (Linux IP server + probe) |
| 12 | Edge-to-cloud FDD pipeline |

## Status

**Planned** — hardware link above is the recommended starting board for RS-485 embedded experiments; firmware track starts after App 16 server/client patterns are stable on Linux.
