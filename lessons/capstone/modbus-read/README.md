# Modbus read CLI (capstone starter)

Optional **beginner-friendly** TCP lab after [Day 36b Modbus TCP](../day36b_modbus_tcp.md).

## Goal

Connect to a Modbus/TCP device, read one holding register, print scaled value—same shape Open-FDD uses at the edge.

## Bench defaults (example)

| Setting | Value |
|---------|--------|
| Host | `192.168.204.14` |
| Port | `1502` |
| Unit ID | `1` |

Override with env or flags when you implement the CLI.

## Suggested flags (clap)

```text
modbus-read --host 192.168.204.14 --port 1502 --unit 1 --register 0 --scale 0.1
```

## Dependencies (when you implement)

- `tokio` + `tokio-modbus` **or** manual MBAP frame on `TcpStream`
- `clap` for `--help` UX (course requirement from Week 6 onward)

## Wireshark

See [wireshark_filters.md](../lab-scripts/wireshark_filters.md) — **`modbus`** or **`tcp.port == 1502`**.

## Related

- Open-FDD Modbus driver @ `192.168.204.14:1502`
- [Vibe Code 18](../../vibe_code_apps_18/) — sanitized lake feeds Open-FDD JSON API

Implement this crate yourself as a **coding challenge**—this README is the spec only.
