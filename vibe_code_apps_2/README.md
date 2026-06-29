# Vibe Code App 2 — RPM apps

**Status:** Done — historical demo (checkpoint **2**).

**ReadPropertyMultiple (RPM)** polling across BACnet devices with **CSV logging** and **daily file rotation**.

## Files

| Script | Stack | What it does |
| --- | --- | --- |
| [`bac0_version_2.py`](./bac0_version_2.py) | BAC0 | Chunked RPM polls → `data_logs/bacnet_rpm_YYYY-MM-DD.csv` |
| [`bacpypes3_version_2.py`](./bacpypes3_version_2.py) | BACpypes3 | Same pattern with bacpypes3 RPM APIs |

## Run (BAC0 example)

```bash
pip install BAC0
python bac0_version_2.py
```

Logs land under `data_logs/` with headers on first write and a new file at local midnight.

## Key concepts

- **RPM chunking** — keep requests small on devices that do not support segmentation (typical MS/TP / low-cost controllers)
- **Daily rotation** — one CSV per day for Excel-friendly trending
- **Poll interval** — configurable `SLEEP_TIME_SECONDS` (default 60 s)

## Related checkpoints

| # | Topic |
| --- | --- |
| 1 | [BAC0 + bacpypes3 basics](../vibe_code_apps_1/) |
| 5 | [Device discovery tools](../vibe_code_apps_5/) |

See the playground [README](../README.md#vibe-code-checkpoints).
