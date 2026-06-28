# Rust lessons lab hub (Days 28–75)

Maps daily lessons to runnable tutorials in this repo. Start Python on [Day 1](../../lessons/day01.md); pivot to Rust on [Day 28](../../lessons/day28.md).

## Track overview

| Phase | Days | Folder / tool |
|-------|------|----------------|
| Rust fundamentals | 28–34 | `cargo new` anywhere; follow [lessons/](../../lessons/) |
| Network + Wireshark | 35–40 | [lessons/lab-scripts/](../../lessons/lab-scripts/) |
| rusty-bacnet | 41–47 | [discover-and-poll capstone](../../lessons/capstone/discover-and-poll/) + upstream [rusty-bacnet](https://github.com/jscott3201/rusty-bacnet) |
| rusty-haystack | 48–54 | [nhaystack-niagara-pi-tutorial/](../nhaystack-niagara-pi-tutorial/) |
| RDF in Rust | 55–75 | [lessons/capstone/](../../lessons/capstone/) (`model/`, `graph-export/`) |

## Capstone bundle (Days 46, 54, 75)

```text
lessons/capstone/
├── discover-and-poll/     ← Day 46 BACnet CLI skeleton
├── niagara-read/        ← pointer to nhaystack-niagara-pi-tutorial (Day 54)
├── graph-export/        ← Day 66/68/75 TTL merge
├── model/ahu1.ttl       ← Day 62 Brick starter
├── pcaps/README.md      ← Day 64/75 Wireshark portfolio
└── COURSE_REVIEW.md     ← Day 74 template
```

Full guide: [lessons/capstone/README.md](../../lessons/capstone/README.md)

## Niagara lab (Days 49–54)

| Script | Purpose |
|--------|---------|
| [01_bash_smoke_test.sh](../nhaystack-niagara-pi-tutorial/scripts/01_bash_smoke_test.sh) | curl `/about` + Basic auth |
| [02_run_rust_smoke.sh](../nhaystack-niagara-pi-tutorial/scripts/02_run_rust_smoke.sh) | Build + run Rust client |
| [03_capture_golden_fixtures.sh](../nhaystack-niagara-pi-tutorial/scripts/03_capture_golden_fixtures.sh) | Day 52 golden captures |
| [04_probe_scram_vs_basic.sh](../nhaystack-niagara-pi-tutorial/scripts/04_probe_scram_vs_basic.sh) | Day 51 auth probe |
| [05_rusty_haystack_niagara_read.sh](../nhaystack-niagara-pi-tutorial/scripts/05_rusty_haystack_niagara_read.sh) | Fork `niagara-read` |

Docs: [nhaystack-niagara-pi-tutorial/README.md](../nhaystack-niagara-pi-tutorial/README.md) · [QUICKSTART.md](../nhaystack-niagara-pi-tutorial/QUICKSTART.md) · [FIXTURES_AND_SIM.md](../nhaystack-niagara-pi-tutorial/FIXTURES_AND_SIM.md)

## Bench profile

Same VLAN as Open-FDD commissioning — see [lessons/capstone/env.example](../../lessons/capstone/env.example).

## Related

- [Lessons INDEX](../../lessons/INDEX.md)
- [Weekly outline](../../README.md#computer-science-theory-101-weekly-outline)
- [rusty-haystack README](../rusty-haystack/README.md)
