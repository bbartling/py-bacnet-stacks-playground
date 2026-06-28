## Day 52 – Golden Fixtures & Offline Haystack Dev

### Goal

Use **golden HTTP fixtures** from the niagara tutorial to develop rusty-haystack parsers without hammering live Niagara.

### Concept

Path: [vibe_code_apps_17/nhaystack-niagara-pi-tutorial/fixtures/](../vibe_code_apps_17/nhaystack-niagara-pi-tutorial/fixtures/) — see [FIXTURES_AND_SIM.md](../vibe_code_apps_17/nhaystack-niagara-pi-tutorial/FIXTURES_AND_SIM.md).

Capture script (run from tutorial folder):

```bash
scripts/03_capture_golden_fixtures.sh
```

Develop pattern:

1. Record real responses once (with permission)
2. Commit redacted **golden** files
3. Unit test client against fixtures (local `mockito` or file:// server—stretch)

### Why This Matters

Network programming best practice: **separate protocol parsing from live I/O** so CI runs without your bench VLAN.

### Mini examples

- Diff `about.zinc` golden vs live `/about`.
- List ops available in fixture metadata.

### Micro exercises

1. Capture golden set on your N4.15 station if not present.
2. Write one test that loads fixture string and asserts row count > 0.
3. Explain replay value when 192.168.204.11 is offline.

### Key takeaway

**Fixtures are how Rust projects test HTTP clients** without always-on Niagara hardware.

### Wireshark Lab

Optional: capture during golden capture script run—filter **`tcp.port == 443`**
