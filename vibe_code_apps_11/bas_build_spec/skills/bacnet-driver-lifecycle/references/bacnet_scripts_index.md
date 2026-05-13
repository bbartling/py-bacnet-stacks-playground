# bacnet_scripts_example index

Human-validated bind args belong in env files or `memory/integrations/bacnet.md` — not committed secrets.

| Script | Role |
|--------|------|
| `point_discovery.py` | Lab Who-Is / object-list discovery |
| `client_device_object_list.py` | Device object list client |
| `client_read_write_release.py` | Read, write, release patterns |
| `client_read_multiple_rpm.py` | Multiple read property multiple |
| `client_priority_array.py` | Priority array interaction |
| `server_schedule_calendar.py` | Schedule/calendar server sample |
| `server_weather_gateway.py` | Weather gateway server sample |

Run only when lab env is set and sign-off is recorded per **`bacnet-driver-lifecycle`** skill.
