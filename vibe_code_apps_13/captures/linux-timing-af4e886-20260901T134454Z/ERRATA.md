# ERRATA — capture `20260901T134454Z`

**Original verdict:** PASS (incorrect)  
**Corrected verdict:** **PARTIAL** — idle phase retained; **loaded phase INVALID**

## Why loaded phase is invalid

1. `stress-ng.log` records immediate failure: `libIPSec_MB.so.1: cannot open shared object file`.
2. Gate script (pre-fix) used `kill -0` on a zombie process, allowing loaded cyclictest to run without real stress.
3. Final result logic overwrote `partial` → `pass` when both cyclictest files contained `T:` lines.
4. No Haystack before/after artifacts despite README claim.
5. Manifest lacked stress-ng exit code, cyclictest version/command, container digest.

## Idle phase (reference only)

| Phase | Min (µs) | Avg (µs) | Max (µs) |
|-------|----------|----------|----------|
| Idle  | 4        | 5        | 365      |

These values are a **host scheduling-risk** indicator vs 1,562.5 µs (60 bit @ 38400). **Not Clause 9 conformance.**

## Replacement

See the post-fix full capture from PR timing evidence closeout (new `linux-timing-af4e886-*` directory).
