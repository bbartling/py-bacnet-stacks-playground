# bas-lite-api

FastAPI app used by **BAS Lite (Docker)**. It imports **easy-aso**’s supervisor (`/api/v1/*`) and adds **legacy** routes under `/app8/api/*` so the existing React SPA keeps working.

**Dependencies:** **`easy-aso[platform]==0.1.5`** is pinned from **PyPI** in `pyproject.toml` (BAS Lite API **v1.5.0** stack line). Rebuild the **`api`** image after changing the pin. Outbound JSON-RPC **Bearer** auth (`BACNET_RPC_API_KEY`) is supported in this **easy-aso** release.

Build and run via repo root `docker-compose.yml`.
