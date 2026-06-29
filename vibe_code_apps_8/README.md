# Vibe Code App 8 — BAS schedule widget demo

**Status:** Done — historical demo (checkpoint **8**).

Frontend UI concepts for **weekly schedules**, **holiday calendars**, and **per-schedule BACnet point lists** — vanilla JS and React variants.

## Subdirectories

| Folder | Stack | README |
| --- | --- | --- |
| [`bas_schedule_widget_demo/vannila/`](./bas_schedule_widget_demo/vannila/) | Plain HTML/CSS/JS | [bas_schedule_widget_demo/README.md](./bas_schedule_widget_demo/README.md) |
| [`bas_schedule_widget_demo/react/`](./bas_schedule_widget_demo/react/) | React + Vite + TypeScript | [bas_schedule_widget_demo/react/README.md](./bas_schedule_widget_demo/react/README.md) |

## Quick start (vanilla)

```bash
cd bas_schedule_widget_demo
python vannila/serve.py
```

Open `http://127.0.0.1:8080/` (override with `PORT` / `BIND` env vars).

## UI features

- **Weekly schedule** — day rows with start/stop; “no schedule” per weekday
- **Holidays** — individual dates or date ranges
- **BACnet points** — stored **per schedule profile** (switch schedules to edit each list)

## Related checkpoints

| # | Topic |
| --- | --- |
| 4 | [BACnet server apps](../vibe_code_apps_4/) — schedule/calendar BACnet objects |
| 9–10 | [diy-bas](../vibe_code_apps_9/) → [integration](../vibe_code_apps_10/) |

See the playground [README](../README.md#vibe-code-checkpoints).
