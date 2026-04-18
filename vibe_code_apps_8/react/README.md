# BAS Schedule Widget Demo

- **Schedule** — Top dropdown (**Select schedule**). The read-only **Weekly calendar** and **Operating week** table always reflect the active schedule only.
- **Operating week** — **Day**, **No schedule** (off / unoccupied that weekday), **Start**, **Stop**. Checked = no block on the calendar; times are disabled until unchecked.
- **Holidays** — **Individual dates** (multi-tap) or **Date range** (click start, then end — span/slide style); add merges days into the list. Unoccupied defaults off; delete rows as needed.
- **BACnet points** — Bottom section; points are **stored per schedule**. Switch schedules to edit each profile’s BACnet list independently.

## Run locally

```bash
npm install
npm run dev
```

```bash
npm run build
npm run preview
```
