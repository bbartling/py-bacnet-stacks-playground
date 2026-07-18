# hvac-bench — absorbed into `wattlab.bench` (deprecated pointer)

The standalone `hvac-bench` package that used to live here has been merged into
the WattLab package in this repo:

- Code: `../wattlab/bench/` (`registry`, `algorithms`, `esco`, `runner`,
  `benchmark`, `models`, `config`, `excel`, `cli`)
- Tests: `../tests/test_bench_*.py`
- Examples: `../examples/bench/`
- Docs: `../docs/bench/`

Install and use via WattLab:

```bash
cd vibe_code_apps_20
pip install -e .
wattlab bench list
```

Python imports change from `hvac_bench.*` to `wattlab.bench.*`:

```python
from wattlab.bench.algorithms import fan_affinity
from wattlab.bench.benchmark import calibration_metrics
```
