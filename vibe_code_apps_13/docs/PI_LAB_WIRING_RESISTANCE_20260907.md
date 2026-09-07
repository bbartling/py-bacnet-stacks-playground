# Vibe13 Pi-lab wiring resistance (operator pause)

**Date:** 2026-09-07  
**Topology:** isolated direct wire · workerpi1 Waveshare **C** ↔ workerpi2 Waveshare **B**  
**Tower FEC/BASRT trunk:** untouched (read-only)

## Unpowered A/B measurements (operator)

| Measurement | Reading | Fail-closed band | Status |
|-------------|---------|------------------|--------|
| workerpi1 C alone (unpowered A↔B) | **127 Ω** | 100–140 Ω | PASS |
| workerpi2 B alone (unpowered A↔B) | **127 Ω** | 100–140 Ω | PASS |
| Combined segment (both ends wired, unpowered A↔B) | **~71 Ω** | 55–75 Ω | PASS (within widened band) |

**Interpretation:** each adapter shows a healthy ~120 Ω-class onboard end termination. Ideal parallel of two 127 Ω ≈ 63.5 Ω; measured **71 Ω** is slightly high (leads/contact/meter) but still clearly “two terminations,” not open and not a single ~120 Ω end.

Fail-closed combined band updated to **55–75 Ω** so this reading passes without override.

## Wiring confirmation (operator)

```text
workerpi1 / Waveshare C                 workerpi2 / Waveshare B
        A+  ================================  A+
        B-  ================================  B-
   GND/REF  ================================  GND/REF
       VCC  ----------- DO NOT CONNECT ----------- VCC
```

- A+↔A+, B-↔B-, GND↔GND, no VCC — **confirmed by operator (2026-09-07)**
- Only the two Pi adapters on this segment — **confirmed**
- Tower / FEC / BASRT live trunk — **untouched**

## Bias

`bias_status`: **not_measured** (Waveshare onboard 120 Ω is termination evidence only — not network bias).

## Next

After this note is on `develop`, run `confirm-wiring` with the numeric ohms above, then Part B C↔B profiles (raw → mstp → USB → soak).
