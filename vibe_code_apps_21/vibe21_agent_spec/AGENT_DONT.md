# WHAT NOT TO DO — Vibe 21 agents (hard lessons)

Read this before touching Unity scenes, WebGL, or deploy zips. These are
**hard fails** that already burned a full twin restore cycle (2026-08-02).

## Unity scene — never gut `Liberty100Twin.unity`

**Incident:** commit `bcc189a` (“ambient 6h day loop…”) deleted ~149k lines from
`Assets/Scenes/Liberty100Twin.unity`. GameObjects went **1128 → 719**, drone
`Body` vanished, `SpinPivot_*` went **4 → 1**, embedded materials shrank. Editor
and WebGL looked “royally fucked” (missing drone pieces, white facade glaze).
Library / Temp wipes and `git checkout` of the **same broken HEAD** did nothing.

### Do not

1. **Do not** “heal”, rewrite, or bulk-edit the YAML scene to fix materials /
   glass / sensors in one giant save. Prefer runtime factories, Editor menu
   tools, or small targeted MCP edits — then `manage_scene(action="save")`.
2. **Do not** add runtime “bootstrap heal” scripts that rebind every
   `MeshRenderer` material on load (`TwinPlayBootstrap`-style). That washed the
   Editor white and masked real dangling refs.
3. **Do not** assume HEAD/`origin/develop` is visually good. After any scene
   change, check **byte size / GO count / drone Body + 4 SpinPivots** before
   declaring restore done:

   ```text
   Good ~12 MB, ~1100+ GameObjects, Body=1, SpinPivot=4
   Bad  ~8 MB,  ~700 GameObjects,  Body=0, SpinPivot=1
   ```

4. **Do not** ship WebGL from a gutted scene. Rebuild player only after Editor
   Play looks correct.
5. **Do not** treat Library wipe as a fix for missing hierarchy. Cache clears
   help import corruption; they do **not** resurrect deleted scene objects.

### Recover

Restore the last intact scene commit (e.g. `91a4746` before the ambient gut),
reopen the scene in Editor (discard dirty in-memory copy), verify Play, then
rebuild WebGL.

```powershell
git checkout 91a4746 -- vibe_code_apps_21/unity/liberty_100/Assets/Scenes/Liberty100Twin.unity
```

## Unity MCP / Editor

1. **Do not** invent room/VAV polygons — Twin JSON only (`UNITY_MCP_WORKFLOW.md`).
2. **Do not** leave milestones unsaved — UI lockups discard progress.
3. **Do not** proceed past compile errors; wait for domain reload + `read_console`.
4. **Do not** train models in Unity — Flask `POST /api/v1/predict/demand_hourly`.

## WebGL / PythonAnywhere

1. **Do not** pack a PA zip without `flask_app/webgl/index.html` + `Build/`
   (packer refuses empty player).
2. **Do not** `pip install` into bare user site for PA — use the **Web tab
   virtualenv**.
3. **Do not** send users to the Files browser URL — app is
   `https://bensapi.pythonanywhere.com/`.
4. **Do not** upload zips > 100 MiB via PA Files page (use SFTP or shrink).

## ML / Flask honesty

1. **Do not** claim BAS-validated demand when status is `CANDIDATE` /
   `ENERGYPLUS_SIMULATED`.
2. **Do not** invent room-level zone temps from the facility kW surrogate —
   Unity badges are DEMO where documented.

## Related

- Workflow: [`UNITY_MCP_WORKFLOW.md`](UNITY_MCP_WORKFLOW.md)
- WebGL handoff: [`UNITY_WEBGL_HANDOFF.md`](UNITY_WEBGL_HANDOFF.md)
- PA deploy: [`PYTHONANYWHERE_DEPLOYMENT.md`](PYTHONANYWHERE_DEPLOYMENT.md)
- Product scope: [`DEMAND_MANAGEMENT_TWIN.md`](DEMAND_MANAGEMENT_TWIN.md)
