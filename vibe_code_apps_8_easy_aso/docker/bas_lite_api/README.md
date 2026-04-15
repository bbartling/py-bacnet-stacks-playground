# bas-lite-api

FastAPI app used by **BAS Lite (Docker)**. It imports **easy-aso**’s supervisor (`/api/v1/*`) and adds **legacy** routes under `/app8/api/*` so the existing React SPA keeps working.

**Dependencies:** `easy-aso[platform]` is installed from **PyPI** (see `pyproject.toml`). Outbound JSON-RPC **Bearer** auth (`BACNET_RPC_API_KEY`) needs **easy-aso ≥ 0.1.5**; when that release is on PyPI, rebuild the image so `pip` resolves the newer wheel. Older PyPI releases omit Bearer on `JsonRpcBacnetClient`.

Build and run via repo root `docker-compose.yml`.
