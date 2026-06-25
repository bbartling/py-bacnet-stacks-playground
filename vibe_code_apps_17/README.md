# Vibe Code App 17 — Project Haystack Playground

Hands-on experiments with [Project Haystack](https://project-haystack.org/) semantic building data — from a Raspberry Pi talking to Niagara **nHaystack**, through Rust ([rusty-haystack](https://github.com/jscott3201/rusty-haystack)), to Python ([pyhaystack](https://github.com/ChristianTremblay/pyhaystack)).

## Subprojects

| Folder | Stack | Upstream | Status |
| --- | --- | --- | --- |
| [nhaystack-niagara-pi-tutorial/](nhaystack-niagara-pi-tutorial/) | Bash + Rust (`reqwest`) | — (this repo) | **Active** — Pi → Niagara nHaystack smoke tests |
| [rusty-haystack/](rusty-haystack/) | Rust workspace + PyO3 bindings | [jscott3201/rusty-haystack](https://github.com/jscott3201/rusty-haystack) | Scaffold — clone/build/play locally |
| [pyhaystack/](pyhaystack/) | Python + hszinc | [ChristianTremblay/pyhaystack](https://github.com/ChristianTremblay/pyhaystack) | Scaffold — venv + Niagara client experiments |

## Recommended order

```text
1. nhaystack-niagara-pi-tutorial  — prove curl/Rust can read from Niagara nHaystack
2. rusty-haystack                 — Haystack types, codecs, client/server in Rust
3. pyhaystack                     — same Niagara station via the mature Python client
```

The first tutorial intentionally uses plain `curl` and a small Rust HTTP client — not rusty-haystack or pyhaystack — so you can isolate network, auth, and nHaystack configuration before adding library complexity.

## Git ignore

- **Repo root** [`.gitignore`](../.gitignore) — shared Python, Rust `target/`, `.env`, and CSV rules
- **This app** [`.gitignore`](.gitignore) — vibe17-specific paths (lab CSV output, maturin artifacts, optional upstream clones)

## Quick links

- [Project Haystack](https://project-haystack.org/)
- [rusty-haystack](https://github.com/jscott3201/rusty-haystack) — Rust core client/server with Python bindings
- [pyhaystack](https://github.com/ChristianTremblay/pyhaystack) — Python client for Niagara, SkySpark, WideSky
- [pyhaystack docs — connecting](https://pyhaystack.readthedocs.io/en/latest/connect.html)
- [nHaystack module (J2 Innovations)](https://www.j2inn.com/nhaystack)
