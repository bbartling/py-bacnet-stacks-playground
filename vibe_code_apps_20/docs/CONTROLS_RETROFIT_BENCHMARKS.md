# Controls retrofit benchmarks

Public, client-neutral screening bands for controls and operational ECMs.

## Data

`wattlab/data/benchmarks/controls_retrofit_public.json`

Loaded by `wattlab.benchmarks.controls_retrofit`.

Each class carries:

- low / typical / high savings bands
- payback range
- savings basis
- source URLs / publication notes
- sample/method/applicability/limitations
- confidence

Placeholder bands are explicitly labeled `screening_placeholder` with low confidence and must never be quoted as guaranteed results.

## Use

Benchmark plausibility → proxy → calibrated EnergyPlus remains the three-layer stack. Benchmarks do not replace bills or simulations.
