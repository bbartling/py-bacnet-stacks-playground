# Synthetic mixed pneumatic / DDC school (conceptual)

Fictional 100,000 ft² school used only for WattLab screening demos. No measured
client data. Controls are mixed pneumatic + old DDC with VAV AHUs, HW reheat,
boiler + CHW plant, IGV fans, and a pneumatic compressor.

## Run (Imperial display defaults)

```powershell
wattlab explore-existing --config examples/synthetic_controls_school/config.yaml --dry-run --out .artifacts/synthetic_controls_school
wattlab ecm package pneumatic-to-ddc
wattlab ecm package partial-g36
```

## Metric twin

`config_metric.yaml` uses the same engineering facts with SI-tagged area
(9,290 m²). Canonical SI results must match after conversion.

```powershell
wattlab explore-existing --config examples/synthetic_controls_school/config_metric.yaml --dry-run --out .artifacts/synthetic_controls_school_si
```

Badge remains `CONCEPTUAL_HYPOTHESIS` without held-out bills.
