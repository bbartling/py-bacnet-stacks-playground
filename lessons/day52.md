# Day 52 – Golden Fixtures & Offline Haystack Dev

## Goal

Use **golden HTTP fixtures** from the niagara tutorial to develop rusty-haystack parsers without hammering live Niagara.

## Concept

Path: [vibe_code_apps_17/nhaystack-niagara-pi-tutorial/fixtures/](../vibe_code_apps_17/nhaystack-niagara-pi-tutorial/fixtures/) — see [FIXTURES_AND_SIM.md](../vibe_code_apps_17/nhaystack-niagara-pi-tutorial/FIXTURES_AND_SIM.md).

Capture script (run from tutorial folder):

```bash
scripts/03_capture_golden_fixtures.sh
```

Develop pattern:

1. Record real responses once (with permission)
2. Commit redacted **golden** files
3. Unit test client against fixtures (local `mockito` or file:// server—stretch)

## Why This Matters

Network programming best practice: **separate protocol parsing from live I/O** so CI runs without your bench VLAN.

## Mini Examples

- Diff `about.zinc` golden vs live `/about`.
- List ops available in fixture metadata.

## Micro Exercises

1. Capture golden set on your N4.15 station if not present.
2. Write one test that loads fixture string and asserts row count > 0.
3. Explain replay value when 192.168.204.11 is offline.

## Wireshark Lab

Optional: capture during golden capture script run—filter **`tcp.port == 443`**

## Key Takeaway

**Fixtures are how Rust projects test HTTP clients** without always-on Niagara hardware.

---

## Python companion — Load a Zinc fixture

*Same day as the Rust lesson above. Prefer a venv; keep scripts in `~/py-lab`.*

```python
from pathlib import Path

# Point at a tutorial golden file when you have one
path = Path("about.zinc")  # or fixtures/about.zinc
text = path.read_text(encoding="utf-8") if path.exists() else 'ver:"3.0"\n'
print("lines:", len(text.splitlines()))
print(text[:120])
```

| Rust (main lesson) | Python |
|--------|--------|
| unit test vs golden Zinc | `pathlib` read + assert line count |
| mockito / file server | offline file only |
| rusty-haystack parse | inspect raw text for intuition |

**Takeaway:** Fixtures are language-agnostic text—parse them in Rust tests; peek in Python if helpful.
