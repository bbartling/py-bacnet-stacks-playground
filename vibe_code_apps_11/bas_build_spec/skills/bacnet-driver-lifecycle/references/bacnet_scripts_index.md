# `bacnet_scripts.md` → driver build map

Authoritative embedded corpus: **`bas_build_spec/bacnet_scripts.md`**. **Runnable** copies for humans and Codex: **`bas_build_spec/bacnet_scripts_example/`** (see **`README.md`** there). Do not paste the whole markdown into prompts.

| Example `.py` | `bacnet_scripts.md` block | BACnet capability | Driver / lab use |
|---------------|---------------------------|-------------------|------------------|
| `point_discovery.py` | Client points discovery (Who-Is sweep) | `who_is` → I-Am → per-device `object-list` | **Human gate** — prove bind + segment before AI work |
| `client_device_object_list.py` | Client points discovery (known instance) | `read_property` `object-list` on one device | Inventory after instance is known |
| `client_read_write_release.py` | Client read / write / release null | `read_property`, `write_property` + `priority`, `Null` relinquish | Supervisory writes; pair with **`safe-bacnet-writes`** |
| `client_read_multiple_rpm.py` | Client read multiple | Chunked RPM, CSV poll loop (`while True`) | Poll adapters, historian ingest |
| `client_priority_array.py` | Client priority array | `priority-array` read | Commandable AO/AV/BO UI |
| `server_schedule_calendar.py` | Server schedule + calendar | `ScheduleObject`, `CalendarObject`, local device | Lab schedule motor; **`bacnet-schedule-motor-verify`** |
| `server_weather_gateway.py` | Server example (weather) | Local AV/BV + external feed loops | **Long-lived gateway** pattern for published points |

## Human-validated `SimpleArgumentParser` args (required)

BACpypes3 apps need CLI args (`--name`, `--instance`, `--address`, optional `--debug`) via **`SimpleArgumentParser`** — not optional defaults invented by automation.

1. Human runs **`point_discovery.py`** with candidate bind until I-Am and object-list look correct.
2. Human records working **`--name`**, **`--instance`**, and **`--address`** in **`memory/integrations/bacnet.md`** (template: **`human_validated_args.env.example`**).
3. AI/driver config **reuses those exact values** for `Application.from_args` / systemd `ExecStart` — do not substitute a different NIC bind or device instance without a new human sign-off.

## Long-running BACpypes3 processes (server / gateway / poll loops)

- **One-shot clients** (read/write, object-list, priority-array): run, exit — fine for lab scripts.
- **Servers, gateways, and poll loops** must stay up: **`while True`** with `asyncio.sleep`, or **`await asyncio.Future()`** after `asyncio.create_task(...)` — mirror **`server_weather_gateway.py`** and **`server_schedule_calendar.py`**, not start/stop the BACpypes3 stack per HTTP request.
- **`bas_app` drivers** that expose BACnet objects or hold a client stack for polling: run under **systemd** as a **long-lived** process using the same asyncio pattern.

## Lab order

1. **`point_discovery.py`** with correct **NIC bind** (`--address IP/prefix:47808`).
2. Sign-off in **`memory/integrations/bacnet.md`** + **`BUILD_CHECKPOINTS.md`** (include validated args).
3. Implement driver adapters from the table — **feature flag off** until sign-off.

## Do not

- Paste all of **`bacnet_scripts.md`** into prompts (see **`GUARDRAILS.md`**).
- Enable on-wire writes in hourly automation before Phase 1 sign-off.
- Ship a BACnet **server** driver that exits after `Application.from_args` without a forever loop.
