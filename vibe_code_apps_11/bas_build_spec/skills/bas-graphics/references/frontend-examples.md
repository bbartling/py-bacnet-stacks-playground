# Frontend example files (roles)

| File | Role |
|------|------|
| `schedule_example.html` | **Operator shell + weekly schedule widget** — 7-day grid, drag/resize blocks, toolbar chrome, Inter/light panel tokens. Production React schedule editor should match this UX. |
| `n4_graphic.html` | **Niagara-style synoptic + logic wire-sheet** — dark plant dashboard, horizontal **flow strip** (nodes, arrows, live values), gauge strips, BAS status colors. Canonical wire-sheet reference. |
| `graphic.html` | **Same bytes as `n4_graphic.html`** (compatibility alias for older prompts). Prefer citing `n4_graphic.html` in new docs. |

Implement wire-sheet strips in the head-end with **your** API/WebSocket bindings — do not ship Niagara BajaScript/RequireJS coupling in `bas_app`.

Supervisory **fan-out** stories (e.g. master OAT → consumer device) appear on the wire-sheet as labeled nodes with live values and arrows; driver details live in `bacnet-driver-lifecycle` and `memory/integrations/bacnet.md`.
