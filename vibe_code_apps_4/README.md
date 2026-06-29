# Vibe Code App 4 — BACnet server apps

**Status:** Done — historical demo (checkpoint **4**).

Mini **BACpypes3 BACnet devices** on the bench: schedules, calendars, and a weather-driven server.

## Files

| Script | What it does |
| --- | --- |
| [`mini-schedule-calendar-device.py`](./mini-schedule-calendar-device.py) | Schedule + calendar objects on a mini device |
| [`mini_weather_device.py`](./mini_weather_device.py) | OpenWeather → BACnet analog/binary values (15 min fetch, 5 s BACnet update) |
| [`open_weather_map_tester.py`](./open_weather_map_tester.py) | Standalone OpenWeather API smoke test |
| [`bacpypes3_read_sched_obj.py`](./bacpypes3_read_sched_obj.py) | Client read of schedule/calendar objects on a remote device |

## Run (weather server example)

```bash
pip install bacpypes3 python-dotenv requests
# Set OPENWEATHER_API_KEY in .env
python mini_weather_device.py --name WebWeatherServer --instance 3456 --debug
```

## BACnet objects (weather server)

| Object | Tag |
| --- | --- |
| `analogValue,1` | dry-bulb temp |
| `analogValue,2` | dewpoint |
| `analogValue,3` | relative humidity |
| `binaryValue,1` | fetch OK flag |

## Related checkpoints

| # | Topic |
| --- | --- |
| 8 | [BAS schedule widget demo](../vibe_code_apps_8/) |
| 4 | Server + client pairing with app **1** read/write labs |

See the playground [README](../README.md#vibe-code-checkpoints).
