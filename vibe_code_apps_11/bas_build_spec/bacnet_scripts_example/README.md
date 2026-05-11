# BACnet lab scripts (human playbooks)

Runnable extracts from `bas_build_spec/bacnet_scripts.md`. Skills link here; do not paste the whole markdown into Codex prompts.

## Human gate (required before AI driver work)

1. Set **this host’s** BACnet bind on the NIC that reaches the segment (`--address IP/prefix:47808` — not the field device IP).
2. Run **`point_discovery.py`** until I-Am and per-device `object-list` look right.
3. Record working **`--name`**, **`--instance`**, and **`--address`** in `bas_build_spec/memory/integrations/bacnet.md` (and sign off in `BUILD_CHECKPOINTS.md`).
4. Only then should automation enable live BACnet or copy args into `bas_app` driver config.

Copy `human_validated_args.env.example` to a local untracked file and fill values after a good discovery run.

## Scripts

| File | Role | Lifetime |
|------|------|----------|
| `point_discovery.py` | Who-Is → I-Am → object-list per device | One-shot |
| `client_device_object_list.py` | object-list on one known device instance | One-shot |
| `client_read_write_release.py` | Read / write / relinquish | One-shot |
| `client_priority_array.py` | Read priority-array | One-shot |
| `client_read_multiple_rpm.py` | RPM poll + CSV | `while True` until Ctrl-C |
| `server_schedule_calendar.py` | Schedule + calendar local device | `await asyncio.Future()` |
| `server_weather_gateway.py` | Local AV/BV + weather loops | `await asyncio.Future()` |

**Head-end drivers:** client poll adapters may loop; **BACnet server / gateway** roles in `bas_app` should run **long-lived** under **systemd** (weather + schedule server patterns), not start/stop the BACpypes3 stack each request.

## Example

```bash
cd /home/ben
python3 bas_build_spec/bacnet_scripts_example/point_discovery.py \
  --name BensReadApp --instance 100 --address 192.168.204.18/24:47808 --debug
```
