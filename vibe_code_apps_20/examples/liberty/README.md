# Liberty campus — shared-meter benchmark example

Two ~140,000 ft² buildings (50 and 100) in Detroit sharing **one electric
meter**, with **building-specific gas meters**. Real monthly bill summaries
(2015 → 2026) used as the practice campus for the WattLab benchmark layer and
the vibe19 → EnergyPlus twin loop.

| File | Contents |
| --- | --- |
| `campus.json` | Buildings, floor areas, meter → building relationships, default allocation |
| `Liberty_50_100_Electric_Summary.csv` | Shared electric: kWh, billed/metered demand kW, power factor, charges |
| `Liberty_50_Gas_Summary.csv` | Building 50 gas (Mcf) — near-zero summers → clean heating-only signature |
| `Liberty_100_Gas_Summary.csv` | Building 100 gas (Mcf) — nonzero summer burn → DHW/reheat baseload signal |

Quick look (latest common 12-month window, Dec 2024 → Nov 2025):

```powershell
wattlab benchmark examples\liberty\campus.json                 # annual EUIs + peer bands
wattlab benchmark examples\liberty\campus.json --scenarios     # allocation modes side-by-side
wattlab studio                                                 # Benchmark page pre-fills this campus
```

Headline numbers (1 kWh = 3,412 Btu, 1 Mcf = 1.037 MMBtu): combined electric
2,928,898 kWh/yr (10.46 kWh/ft²); campus site EUI 71.6 kBtu/ft²-yr — nearly on
the CBECS all-commercial average of 70.6. Per-building EUI depends on how the
shared electric meter is split (50/50: 66.9 vs 76.3; gas-share proxy: 62.2 vs
81.0), which is exactly why allocation is a visible scenario in the tool, not
a buried assumption.

Data quirks the loader handles (and tests pin): duplicate bill months from
split billing periods (summed), quoted thousands separators, missing months
(the common-window finder skips them), and $/Mcf outliers on near-zero months.
