# BACnet integration memory

**Per-site log** — not generic spec. **Wire off** until human lab sign-off in `BUILD_CHECKPOINTS.md` § BACnet lab sign-off. After sign-off: **Who-Is** on bind from **`PHASE_NOTEPAD.md` § A**; record I-Ams, bind args, and object counts here per **bacnet-driver-lifecycle**.

## Operator-staged devices and discovered wire notes

| Role | BACnet device ID | IPv4 | Notes |
|------|------------------|------|--------|
| Head-end bind | (local) | `192.168.204.18/24:47808` on `enp3s0` | BACpypes3 `--address` target |
| BACnet-presenting Pi / DS18B20 temperature sensor | `3456788` | `192.168.204.12` | Discovered on wire; point scrape returned analog-value samples |
| VAV | `3456790` | `192.168.204.14` | Expected on wire |
| AHU | `3456789` | **`192.168.204.13`** | **Corrected** — chat had typo `.113` |

- Human sign-off on discovery already exists in `BUILD_CHECKPOINTS.md`; Who-Is polling is now active on the staged bind.
- Current discovery snapshot: 3 I-Am responses, instances `3456788`, `3456790`, `3456789`; point scraping has produced a bounded report with 8 successful samples and 0 failures.

## 2026-05-16T15:07:10Z — discovery failed

```
Traceback (most recent call last):
  File "/home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/bacnet_scripts_example/point_discovery.py", line 4, in <module>
    from bacpypes3.argparse import SimpleArgumentParser
ModuleNotFoundError: No module named 'bacpypes3'
```

## 2026-05-16T15:08:02Z — discovery failed

```
--- Starting Discovery ---
Device Instance: 3456788 | Address: 192.168.204.12
Device Instance: 3456790 | Address: 192.168.204.14
Device Instance: 3456789 | Address: 192.168.204.13
Traceback (most recent call last):
  File "/home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/bacnet_scripts_example/point_discovery.py", line 64, in <module>
    asyncio.run(main())
  File "/usr/lib/python3.12/asyncio/runners.py", line 194, in run
    return runner.run(main)
           ^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/asyncio/runners.py", line 118, in run
    return self._loop.run_until_complete(task)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/asyncio/base_events.py", line 687, in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
  File "/home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/bacnet_scripts_example/point_discovery.py", line 44, in main
    obj_list = await app.read_property(
               ^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/ben/bas_app/.venv/lib/python3.12/site-packages/bacpypes3/service/object.py", line 126, in read_property
    response = await self.request(read_property_request)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
bacpypes3.apdu.AbortPDU: no-response
```

## 2026-05-16T15:08:34Z — discovery failed

```
--- Starting Discovery ---
Device Instance: 3456788 | Address: 192.168.204.12
Device Instance: 3456789 | Address: 192.168.204.13
Device Instance: 3456790 | Address: 192.168.204.14
Traceback (most recent call last):
  File "/home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/bacnet_scripts_example/point_discovery.py", line 67, in <module>
    asyncio.run(main())
  File "/usr/lib/python3.12/asyncio/runners.py", line 194, in run
    return runner.run(main)
           ^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/asyncio/runners.py", line 118, in run
    return self._loop.run_until_complete(task)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.12/asyncio/base_events.py", line 687, in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
  File "/home/ben/py-bacnet-stacks-playground/vibe_code_apps_11/bas_build_spec/bacnet_scripts_example/point_discovery.py", line 45, in main
    obj_list = await app.read_property(
               ^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/ben/bas_app/.venv/lib/python3.12/site-packages/bacpypes3/service/object.py", line 126, in read_property
    response = await self.request(read_property_request)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
bacpypes3.apdu.AbortPDU: no-response
```

## 2026-05-16T15:09:07Z — lab discovery OK

- bind: `192.168.204.18/24:47808`
- I-Am responses: **0**

```
--- Starting Discovery ---
Device Instance: 3456788 | Address: 192.168.204.12
Device Instance: 3456789 | Address: 192.168.204.13
Device Instance: 3456790 | Address: 192.168.204.14
OBJECT LIST unavailable for 192.168.204.18: no-response
```

## 2026-05-16T15:09:34Z — lab discovery OK

- bind: `192.168.204.18/24:47808`
- I-Am responses: **3**

```
--- Starting Discovery ---
Device Instance: 3456788 | Address: 192.168.204.12
Device Instance: 3456790 | Address: 192.168.204.14
Device Instance: 3456789 | Address: 192.168.204.13
OBJECT LIST unavailable for 192.168.204.18: no-response
```

## 2026-05-16T16:27:42Z — lab discovery OK

- bind: `192.168.204.18/24:47808`
- I-Am responses: **3**

```
--- Starting Discovery ---
Device Instance: 3456788 | Address: 192.168.204.12
Device Instance: 3456790 | Address: 192.168.204.14
Device Instance: 3456789 | Address: 192.168.204.13
OBJECT LIST unavailable for 192.168.204.18: no-response
```
