# Domain memory (local only)

**Not committed to Git.** Templates live in `../templates/`. Initialize with:

```bash
vibe12_agent_spec/bin/vibe12_workspace_init.sh
```

| Path | Purpose |
|------|---------|
| `commissioning/PHASE_NOTEPAD.md` | Site bind, devices, URLs (human + agent) |
| `sites/` | Per building stable facts |
| `stack/` | Edge + cloud runtime |
| `integrations/` | AWS IoT, MQTT |
| `architecture/working-divergence.md` | Doc vs runtime gaps |
| `YYYY-MM-DD.md` | Daily agent log (append-only) |

Promote durable facts to `../MEMORY.md` after critique. Never store secrets here.
