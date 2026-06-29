# Vibe Code App 3 — Priority array tools

**Status:** Done — historical demo (checkpoint **3**).

Inspect BACnet **priority arrays**, operator overrides, and control authority on commandable points.

## Files

| Script | Stack | What it does |
| --- | --- | --- |
| [`BAC0_version_3.py`](./BAC0_version_3.py) | BAC0 | `read_priority_array()` on `analog-value,3` |
| [`bacypes_version_3.py`](./bacypes_version_3.py) | BACpypes3 | Read and interpret priority slots via `Application` |

## Run (BAC0 example)

```bash
pip install BAC0
python BAC0_version_3.py
```

Edit `DEVICE_IP`, `READ_OBJ_TYPE`, and `READ_INSTANCE` for your bench device.

## Run (BACpypes3 example)

```bash
pip install bacpypes3
python bacypes_version_3.py --address 192.168.204.11/24:47808 --debug
```

## Key concepts

- **Priority array** — sixteen slots; lower number = higher authority
- **present-value** — effective value after priority resolution
- **Overrides** — non-null slot means something is commanding the point

## Related checkpoints

| # | Topic |
| --- | --- |
| 1 | [BAC0 + bacpypes3 basics](../vibe_code_apps_1/) |
| 4 | [BACnet server apps](../vibe_code_apps_4/) |

See the playground [README](../README.md#vibe-code-checkpoints).
