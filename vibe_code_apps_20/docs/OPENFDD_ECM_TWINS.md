# Open-FDD ECM twins vs local-only WattLab calculators

Registry names stay stable (`wattlab.bench.registry`). As of Open-FDD **4.1.x**,
only these **8** calculators have name-matched Open-FDD implementations and are
**delegated** through `wattlab.engineering.openfdd_ecm`:

| WattLab `@register` name | Open-FDD surface |
|---|---|
| `fan_affinity` | `open_fdd.ecm_engineering.calculate` |
| `schedule_reduction` | same |
| `outside_air_sensible` | same (WattLab default fuel=`electric`) |
| `kw_per_ton_improvement` | same |
| `boiler_efficiency_improvement` | same |
| `scheduling_fan_bins` | `bin_methods` via adapter |
| `scheduling_cooling_bins` | same |
| `scheduling_heating_bins` | same |

## Intentional local-only keepers (no Open-FDD equivalent in 4.1.x)

Do **not** delete or silently map these to similarly named proxies:

`demand_control_ventilation`, `economizer_proxy`, `pump_vfd`, `temperature_reset_bins`,
`eui`, `simple_payback`, `heat_pump_electrification`, `oad_unoccupied_closed`,
`dcv_bins`, `static_pressure_reset`, `dat_reset_bins`, `hydronic_reset_bins`,
`chw_reset`, `condenser_water_reset`, `pneumatic_compressor`, `dewpoint_economizer`,
`erv_bins`, `toilet_exhaust_erv_bins`

(`economizer_proxy` ≠ `economizer_runtime_cap`; `chw_reset` ≠ `chws_reset_proxy`; etc.)

Parity evidence: `tests/test_openfdd_ecm_parity.py` + golden `tests/test_esco_golden.py`.
