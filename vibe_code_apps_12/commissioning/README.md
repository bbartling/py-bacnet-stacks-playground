# Commissioned BACnet points

## Public vs private

| Tree | Git | Use |
|------|-----|-----|
| `commissioning/_examples/` | **Yes** | Synthetic multi-building samples for docs |
| `commissioning/local/` | **No** (gitignored) | Real `points.csv` from `./fetch_commissioning.sh` |
| `commissioning/{site}/{building}/host.yml` | **No** (gitignored) | Contains gateway IP — never commit |

**Guide:** [ansible/PRIVATE-MULTI-SITE.md](../ansible/PRIVATE-MULTI-SITE.md)

## Fetch from edge (writes to `local/` by default)

```bash
cd ansible
./fetch_commissioning.sh --limit acme_tower_a -v
# → commissioning/local/acme/tower-a/points.csv
```

Canonical operator doc: [docs/commissioning-backup.md](../docs/commissioning-backup.md)
