# Multi-agent runtime and RPC-docked agents — draft for **easy-aso** repository

> **Purpose:** Paste or adapt this document into the **easy-aso** repo (e.g. `docs/MULTI_AGENT_RUNTIME.md` or an RFC issue). Demo repos such as **py-bacnet-stacks-playground** should stay **thin**: Compose services, `.env`, and **declarative agent definitions**—not duplicate runtime code.

---

## 1. Goals

| Goal | Description |
|------|-------------|
| **One BACnet edge** | A single process (or dedicated gateway container) owns **BACnet/IP UDP**; agents never compete for port 47808. |
| **Many control agents** | Arbitrary **EasyASO subclasses** run in **separate processes/containers**, each with `on_start` / `on_step` / `on_stop`. |
| **PyPI is source of truth** | `easy-aso` ships **RpcDockedEasyASO**, **runner CLI**, **manifest schema**, and **env conventions**. Demos only **pin a version** and **point config at classes**. |
| **Optional orchestration** | **Docker Compose**, systemd, or a future “agent manager” are **deployments**; the library exposes a **stable contract** they can call. |

Non-goals for **v1** in the library:

- Owning Docker or Kubernetes APIs (belongs in deployment repos or a small **agent-manager** sidecar).
- Implementing full VOLTTRON parity (VIP bus, historian, etc.).

---

## 2. Conceptual model (VOLTTRON analogy)

| VOLTTRON idea | easy-aso mapping |
|---------------|------------------|
| Platform | **Supervisor** (`api` container) + **BACnet gateway** (e.g. diy-bacnet JSON-RPC) |
| Platform driver (BACnet) | **Single** gateway; `JsonRpcBacnetClient` as the **edge driver** from agents |
| Agent | **EasyASO subclass**; **RpcDockedEasyASO** when I/O is RPC-only |
| Many agents | **N processes/containers**, each `pip install easy-aso==X` and same **RPC URL + auth** |

---

## 3. Proposed package layout (inside **easy-aso**)

```
easy_aso/
  easy_aso.py                    # unchanged public surface
  bacnet_client/
    jsonrpc_client.py
  runtime/
    __init__.py
    rpc_docked.py                # RpcDockedEasyASO (moved from demos)
    transports/
      __init__.py
      jsonrpc.py                 # optional: thin wrapper + env → client factory
    runner.py                    # importlib + asyncio.run(agent.run())
    env.py                       # parse SUPERVISOR_BACNET_RPC_* / EASY_ASO_AGENT_* 
    manifest.py                  # load/validate agent manifest (dataclass + JSON Schema)
    heartbeat.py                 # optional HTTP POST or callback hook (P1)
  cli/
    __init__.py
    agent.py                     # console_scripts: easy-aso-agent = easy_aso.cli.agent:main
```

**Optional** (later) top-level extras in `pyproject.toml`:

- `[project.optional-dependencies] agents = []` — nothing extra, or `agents = ["jsonschema"]` if manifest validation pulls it in.

---

## 4. Public API (minimal v1)

### 4.1 `RpcDockedEasyASO`

**Module:** `easy_aso.runtime.rpc_docked`

- Subclasses **`EasyASO`**.
- **`async def create_application(self) -> None`**: construct **`JsonRpcBacnetClient`** from **typed config** (see §5); set `self.app = None`; keep `optimization_enabled_bv` placeholder behavior compatible with core `EasyASO`.
- **`async def close_rpc_dock(self) -> None`**: idempotent close of HTTP client.
- **`bacnet_read` / `bacnet_write`**: delegate to `_rpc` (same signatures as `EasyASO`).
- **`bacnet_rpm`**: default `NotImplementedError` with docstring pointing to per-object reads unless gateway adds RPM later.

**Config source:** Prefer **`BacnetRpcConfig`** dataclass passed explicitly in tests; production uses **`from_env()`** in `easy_aso.runtime.env`.

### 4.2 Runner

**Module:** `easy_aso.runtime.runner`

```python
def run_agent_class(
    module: str,
    class_name: str,
    *,
    no_bacnet_server: bool = True,
) -> None:
    """Set sys.argv for EasyASO, import module, instantiate class, asyncio.run(agent.run())."""
```

Environment fallbacks (if `module`/`class_name` are `None`):

- `EASY_ASO_AGENT_MODULE`
- `EASY_ASO_AGENT_CLASS`

### 4.3 CLI (entry point)

**Console script:** `easy-aso-agent`

```text
easy-aso-agent run [--module MOD] [--class CLASS]
```

Defaults read from env; intended **Docker CMD**: `easy-aso-agent run`.

---

## 5. Configuration contract (env + optional manifest)

### 5.1 Environment variables (canonical names)

Shared with supervisor and demos:

| Variable | Meaning |
|----------|---------|
| `SUPERVISOR_BACNET_RPC_URL` | Base URL (no trailing slash), e.g. `http://diy-bacnet:8080` |
| `SUPERVISOR_BACNET_RPC_ENTRYPOINT` | Path prefix, e.g. `/api` |
| `BACNET_RPC_API_KEY` | Optional Bearer token for outbound RPC |

Agent identity (runner):

| Variable | Meaning |
|----------|---------|
| `EASY_ASO_AGENT_MODULE` | Dotted import path, e.g. `my_site.agents.oat_bridge` |
| `EASY_ASO_AGENT_CLASS` | Class name, e.g. `OatBridgeAgent` |

Optional tuning (agent-defined; document only as **conventions**, not required by core):

| Variable | Meaning |
|----------|---------|
| `EASY_ASO_STEP_SEC` | Hint for sleep between `on_step` in sample agents |
| `EASY_ASO_LOG_LEVEL` | `INFO`, `DEBUG`, … |

**Implementation:** `easy_aso.runtime.env.load_rpc_config()` → `BacnetRpcConfig`.

### 5.2 Agent manifest (JSON or YAML) — P1 but specify now

Path: `EASY_ASO_MANIFEST_PATH` or embed in Compose `labels` as base64 (avoid if possible).

**Purpose:** Declarative metadata for UI, policy, and **future** agent-manager without Python imports.

```yaml
# easy_aso_agent_manifest v1
schema_version: 1
agent_id: oat-share-001
display_name: "OAT share bridge"
entry:
  module: my_site.agents.oat
  class: OatAgent
runtime:
  easy_aso_version_pin: ">=0.1.5,<0.2"
bacnet:
  mode: jsonrpc_only           # future: msapi, etc.
rpc:
  url: ${SUPERVISOR_BACNET_RPC_URL}   # substitution optional
  entrypoint: ${SUPERVISOR_BACNET_RPC_ENTRYPOINT}
policies:                        # P2 — optional write scopes
  write_allow:
    - device: "10.0.1.5"
      objects: ["analog-value,2"]
```

Ship **`easy_aso/runtime/schemas/agent_manifest_v1.json`** (JSON Schema) and validate in **`easy_aso.runtime.manifest`**.

---

## 6. Logging and observability (P1)

- **Structured log line prefix:** `easy_aso.agent_id=<id>` when `EASY_ASO_AGENT_ID` set.
- **`easy_aso.runtime.heartbeat`:** optional periodic POST to `EASY_ASO_HEARTBEAT_URL` with JSON `{"agent_id","status","step"}` — **off by default**; demos enable via env.

---

## 7. Version compatibility

- **`easy_aso.__version__`** checked by runner on startup (warning only in v1; hard fail optional via `EASY_ASO_STRICT_VERSION=1`).
- **Manifest** `runtime.easy_aso_version_pin` validated with **`packaging.specifiers`** if present.

---

## 8. What demo repos keep after this lands (config-only ideal)

| Artifact | Demo repo responsibility |
|----------|-------------------------|
| `docker-compose.yml` | Services: `diy-bacnet`, `api`, `frontend`, **minimal agent image** that `FROM python:…` + `pip install easy-aso[platform]==X` + `CMD easy-aso-agent run` |
| `.env` | RPC URL, API key, `EASY_ASO_AGENT_*` |
| `agents/` or single wheel | **Only** site-specific subclasses (or private package); **no** copy of `RpcDockedEasyASO` |
| Docs | Link to **easy-aso** published docs for multi-agent |

**Example minimal Dockerfile** (demo):

```dockerfile
FROM python:3.12-slim
RUN pip install --no-cache-dir "easy-aso[platform]==0.1.6"
COPY agents/ /app/agents/
WORKDIR /app
ENV PYTHONPATH=/app
CMD ["easy-aso-agent", "run"]
```

---

## 9. Migration checklist (from current BAS Lite demo)

1. **Release** `easy-aso` with `easy_aso.runtime.rpc_docked`, `runner`, `cli.agent`.
2. Bump pin in **`bas_lite_api`** and agent images to that release.
3. **Delete** duplicated `rpc_docked_easy_aso.py` / shim **`run_agent.py`** from demo Docker contexts; replace **`CMD`** with **`easy-aso-agent run`**.
4. Keep **Compose profiles** (`oat`, `agents`) as **pure config**.
5. Optional: add **`agent_manifest_v1`** validation in a future **`agent-manager`** service (separate repo or demo).

---

## 10. Phased delivery

| Phase | Scope |
|-------|--------|
| **P0** | Move **RpcDockedEasyASO** + **runner** + **`easy-aso-agent` CLI** + **`env.load_rpc_config`** into **easy-aso**; tests; docs page **Multi-agent (RPC-docked)**. |
| **P1** | **Manifest** schema + validator; **heartbeat** hook; **`EASY_ASO_AGENT_ID`** logging. |
| **P2** | **Write policy** enforcement (library helper; enforcement host may be supervisor or manager). |
| **P3** | Optional **RPM** over RPC if gateway exposes a batch method (gateway-specific). |

---

## 11. Test matrix (upstream)

- Unit: `RpcDockedEasyASO.create_application` mocks `JsonRpcBacnetClient`.
- Integration: mock HTTP server matching diy-bacnet JSON-RPC contract.
- CLI: `easy-aso-agent run` with `EASY_ASO_AGENT_MODULE/CLASS` pointing at a trivial subclass.

---

## 12. Appendix — Issue titles for **easy-aso** tracker

1. `[P0] Add easy_aso.runtime.rpc_docked.RpcDockedEasyASO`
2. `[P0] Add easy_aso.runtime.runner + easy-aso-agent CLI`
3. `[P0] Document env vars SUPERVISOR_BACNET_RPC_* / EASY_ASO_AGENT_*`
4. `[P1] agent_manifest_v1 JSON Schema + manifest.load()`
5. `[P1] Optional heartbeat URL emitter`
6. `[P2] Write-scope policy helper (no enforcement by default)`

---

**End of draft** — copy into **easy-aso** and trim or expand as maintainers prefer.
