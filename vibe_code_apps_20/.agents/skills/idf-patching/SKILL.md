# Skill: idf-patching

Apply WattLab-owned IDF text patches for ECMs EnergyPlus-MCP cannot fully edit yet.

## Patches

| Name | Module | Intent |
|---|---|---|
| `fan_avail_continuous` | `idf_patches/schedules.py` | 24/7 fan/coil availability (SCHED-247 baseline) |
| `fan_avail_occupied_office` | `idf_patches/schedules.py` | Weekday occupied availability |
| `gl36_airside_proxy` | `idf_patches/gl36_proxy.py` | VAV min + fan pressure / min-flow proxies |

## Rules

- Always copy IDF before patching; hash with `results_parse.file_sha256`
- Label GL36 work `conceptual_gl36_proxy` / `gl36_proxy_not_full_sequences`
- One approved measure → one patch → one resimulate
