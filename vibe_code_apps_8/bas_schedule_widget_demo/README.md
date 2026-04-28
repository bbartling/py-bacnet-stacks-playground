# BAS Schedule Widget Demo

- **Schedule** — Top dropdown (**Select schedule**). The read-only **Weekly calendar** and **Operating week** table always reflect the active schedule only.
- **Operating week** — **Day**, **No schedule** (off / unoccupied that weekday), **Start**, **Stop**. Checked = no block on the calendar; times are disabled until unchecked.
- **Holidays** — **Individual dates** (multi-tap) or **Date range** (click start, then end — span/slide style); add merges days into the list. Unoccupied defaults off; delete rows as needed.
- **BACnet points** — Bottom section; points are **stored per schedule**. Switch schedules to edit each profile’s BACnet list independently.

## Run locally (vanilla only)

The demo in `vannila/` is plain HTML/CSS/JS. Serve it with Python’s built-in HTTP server (stdlib only, no Node):

```bash
python vannila/serve.py
```

Run from the repo root (path as above) or from `vannila/` as `python serve.py`. Open the URL printed in the terminal (default `http://127.0.0.1:8080/`).

Optional environment variables: `PORT` (default `8080`), `BIND` (default `127.0.0.1`). Example — PowerShell: `$env:PORT='9000'; python vannila/serve.py`

For the separate React/Vite app under `react/`, see `react/README.md`.
