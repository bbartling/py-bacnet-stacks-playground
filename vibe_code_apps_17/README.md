# Vibe Code App 17 — Project Haystack Playground

Hands-on experiments with [Project Haystack](https://project-haystack.org/) semantic building data — from a Pi/Linux host talking to **Niagara 4.15 nHaystack**, through golden fixtures, Rust ([rusty-haystack](https://github.com/jscott3201/rusty-haystack)), Python ([pyhaystack](https://github.com/ChristianTremblay/pyhaystack)), to **Open-FDD** driver integration.

## Subprojects

| Folder | Stack | Upstream | Status |
| --- | --- | --- | --- |
| [rust-lessons/](rust-lessons/) | Lesson map + capstone links | — (this repo) | **Active** — Days 28–75 Rust track hub |
| [nhaystack-niagara-pi-tutorial/](nhaystack-niagara-pi-tutorial/) | Bash + Rust + golden fixtures | — (this repo) | **Active** — N4.15 lab, Basic auth, SCRAM probe, fixture capture |
| [rusty-haystack/](rusty-haystack/) | Rust workspace + PyO3 bindings | [jscott3201/rusty-haystack](https://github.com/jscott3201/rusty-haystack) / [bbartling fork](https://github.com/bbartling/rusty-haystack) | AuthMode::Basic for Niagara |
| [pyhaystack/](pyhaystack/) | Python + hszinc | [ChristianTremblay/pyhaystack](https://github.com/ChristianTremblay/pyhaystack) | Scaffold |

## Recommended order

```text
0. lessons/day28–75 + lessons/capstone/     — Rust networking course + portfolio skeleton
1. nhaystack-niagara-pi-tutorial             — curl/Rust + golden capture (Niagara 4.15.3.28)
2. FIXTURES_AND_SIM.md                       — plan nHaystack API double (no Tridium)
3. rusty-haystack                            — HaystackClient Basic auth against same URL
4. pyhaystack                                — Python client parity
5. Open-FDD                                  — Haystack driver + MCP bench profile
```

**Rust lessons hub:** [rust-lessons/README.md](rust-lessons/README.md) — maps Days 28–75 to tutorials and capstone crates.

## Lab station reference

```text
Niagara 4 (N4) 4.15.3.28  |  nHaystack 3.3.0.0  |  https://192.168.204.11/haystack
User open_fdd + HTTPBasicScheme (not Haystack SCRAM)
```

## Git ignore

- **Repo root** [`.gitignore`](../.gitignore)
- **Golden captures** `**/fixtures/golden/` — local only; see `fixtures/example/` for committed samples

## Quick links

- [Project Haystack](https://project-haystack.org/)
- [rusty-haystack](https://github.com/jscott3201/rusty-haystack)
- [pyhaystack connecting](https://pyhaystack.readthedocs.io/en/latest/connect.html)
- [nHaystack (J2 Innovations)](https://www.j2inn.com/nhaystack)
