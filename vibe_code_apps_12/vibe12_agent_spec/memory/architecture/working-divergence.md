# Working divergence log

Append when docs/skills disagree with verified runtime.

## 2026-05-25 — IoT policy wildcards

- **Expected (early doc):** `topic/vibe12/*` single-level wildcard is enough.
- **Reality:** Device publish to `vibe12/demo/bens-office/.../telemetry` required `topic/vibe12/+/+/+/+/telemetry` or explicit `topic/vibe12/demo/bens-office/*`.
- **Status:** fixed in AWS policy v4+; documented in `aws-iot.md` and skills.

## 2026-05-25 — Commissioning API path segments

- **Bug:** `/api/telemetry/flow/{site}/{building}` parsed site as `flow`.
- **Fix:** deploy revision 8; test `tests/test_telemetry_api_routes.py`.
