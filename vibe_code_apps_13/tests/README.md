# Test Evidence Layout

Recommended naming:

```text
tests/unit/
tests/integration/
tests/hardware/
reports/phase1-*.json
reports/phase2-*.json
reports/phase3-*.json
captures/<phase>/<date>/
```

Hardware and soak tests are opt-in and ignored by default. Each result records the exact source commit, Linux/kernel, USB devices, driver/by-id paths, baud, wiring/termination/bias and fault injections.

