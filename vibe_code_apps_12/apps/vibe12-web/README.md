# Vibe12 Cloud (React SPA)

Served from **Lambda** only (`web_lambda/static/app/`) — build before SAM deploy.

## Requirements

- **Node.js** `>=20.19.0` (Vite 7.3+ and `@vitejs/plugin-react` 5.2+ enforce this; use **Node 22** in CI)
- npm 10+

Check: `node -v` — if you see `20.18.x`, upgrade Node or use `nvm install 22`.

## Scripts

```bash
npm ci
npm run dev      # http://localhost:5174
npm test         # vitest
npm run build    # dist/ → copied by ../../scripts/build_web_ui.sh
```

## Dependency policy (May 2026)

| Package | Pinned | Notes |
|---------|--------|--------|
| **vite** | ^7.3.3 | Latest **7.x** stable. **Vite 8** exists (8.0.14) but requires `@vitejs/plugin-react` **6.x** (drops Vite 7). Upgrade together. |
| **@vitejs/plugin-react** | ^5.2.0 | Pairs with Vite 7. **6.0.2** is for Vite 8 only. |
| **react** / **react-dom** | ^19.2.6 | Current npm stable |
| **react-router-dom** | ^7.15.1 | Current 7.x |
| **vitest** | ^4.1.7 | Matches Vite 7 ecosystem |
| **typescript** | ~5.9.3 | Stay on 5.x until Vite/tsconfig migration to TS 6 |

GH Dependabot: prefer **patch/minor** within the table above; do not downgrade `plugin-react` to 4.x (older major).

## Upgrade path to Vite 8 (later)

1. Node 22+ on dev machines.
2. `vite@^8.0.14`, `@vitejs/plugin-react@^6.0.2`
3. Re-run `npm run build` and `./scripts/build_web_ui.sh`
