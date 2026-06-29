# Vibe Code App 1 — BAC0 + bacpypes3 basics

**Status:** Done — historical demo (checkpoint **1**).

First BACnet read/write scripts comparing **BAC0** and **BACpypes3** on the bench.

## Files

| Script | Stack | What it does |
| --- | --- | --- |
| [`bac0_version_1.py`](./bac0_version_1.py) | BAC0 | Who-Is discovery, read `present-value`, write at priority **10**, release with **`NULL`** |
| [`bacpypes3_version_1.py`](./bacpypes3_version_1.py) | BACpypes3 | Same flow using `Application`, `read_property`, `write_property`, priority array release |

## Run (BACpypes3 example)

```bash
pip install bacpypes3
python bacpypes3_version_1.py --name BensReadApp --instance 100 --address 192.168.204.11/24:47808
```

Edit `DEVICE_IP`, `READ_POINT`, and `WRITE_POINT` at the top of each script for your bench.

## Key concepts

- **ReadProperty** — `analog-input,1 present-value`
- **WriteProperty** — operator override at priority **10**
- **Release** — write **`NULL`** at the same priority to hand control back
- **Who-Is** — discovery only in lab; avoid flooding production networks

## Related checkpoints

| # | Topic |
| --- | --- |
| 2 | [RPM apps](../vibe_code_apps_2/) |
| 3 | [Priority array tools](../vibe_code_apps_3/) |

See the playground [README](../README.md#vibe-code-checkpoints).
