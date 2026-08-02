# WHAT NOT TO DO — Vibe 21 agents (hard lessons)

Read this before touching Unity scenes, WebGL, or deploy zips. These are
**hard fails** that already burned restore / blank-WebGL / hour-long compile
cycles (2026-08-02).

## Unity scene — never gut `Liberty100Twin.unity`

**Incident:** commit `bcc189a` (“ambient 6h day loop…”) deleted ~149k lines from
`Assets/Scenes/Liberty100Twin.unity`. GameObjects went **1128 → 719**, drone
`Body` vanished, `SpinPivot_*` went **4 → 1**, embedded materials shrank. Editor
and WebGL looked broken (missing drone pieces, white facade glaze). Library /
Temp wipes and `git checkout` of the **same broken HEAD** did nothing.

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
5. **Do not** open the Editor while a headless `-batchmode` WebGL build owns the
   project — you will fight the lock. Wait for the batch job to quit first.

## WebGL — blank sky + audio only (2026-08-02)

**Symptom:** browser WebGL loads, motor/UI sounds work, **no building / drone /
meshes**. Editor Play is fine.

**Root causes that stacked:**

1. WebGL platform quality defaulted to **Mobile** URP while Editor used **PC**.
2. Batch build used **`-nographics`** → URP variants / player incomplete for GLES.
3. Turning **Strip Unused Variants = off** to “fix” visibility caused **thousands**
   of shader compiles (hours) — kill that approach; not needed for PA size.

### Do not

1. **Do not** pack a PA zip without `flask_app/webgl/index.html` + `Build/`
   (packer refuses empty player).
2. **Do not** build WebGL with Unity `-nographics`.
3. **Do not** leave WebGL quality on Mobile when the twin was authored on PC URP —
   set `QualitySettings` **WebGL → PC** (index 1). Build pipeline also forces
   `QualitySettings.SetQualityLevel(1)` in `LibertyWebGLBuildPipeline`.
4. **Do not** set URP `Strip Unused Variants = off` for demos — keep stripping
   **on**; fix visibility with PC quality + graphics batchmode instead.
5. **Do not** `pip install` into bare user site for PA — use the **Web tab
   virtualenv**.
6. **Do not** send users to the Files browser URL — app is
   `https://bensapi.pythonanywhere.com/`.
7. **Do not** upload zips > 100 MiB via PA Files page (use SFTP or shrink).

### Blessed build + pack (blog / PA day)

```powershell
cd vibe_code_apps_21
# Editor closed. Headless WITH graphics (no -nographics):
powershell -File tools/build_webgl_pa.ps1
# → flask_app/webgl/ refreshed
# → dist/vibe21_pa_bundle.zip  (~25–27 MiB typical, must be ≤100 MiB)
```

Local smoke: `python -m flask_app` → http://127.0.0.1:5050/ (hard-refresh after rebuild).

Expected zip contents: flat `flask_app.py`, `twin_api/` (+ `demand_hourly_v2`),
`webgl/`, `requirements.txt`.

## ML / Flask honesty

1. **Do not** claim BAS-validated demand when status is `CANDIDATE` /
   `ENERGYPLUS_SIMULATED`.
2. **Do not** invent room-level zone temps from the facility kW surrogate —
   Unity badges are DEMO where documented.
3. Blog / GH notebook: `notebooks/demand_hourly_training_walkthrough.ipynb`
   (executed with embedded plots). HTML mirror: Flask `/notebooks/demand_hourly`.

## Related

- Workflow: [`UNITY_MCP_WORKFLOW.md`](UNITY_MCP_WORKFLOW.md)
- WebGL handoff: [`UNITY_WEBGL_HANDOFF.md`](UNITY_WEBGL_HANDOFF.md)
- PA deploy: [`PYTHONANYWHERE_DEPLOYMENT.md`](PYTHONANYWHERE_DEPLOYMENT.md)
- Product scope: [`DEMAND_MANAGEMENT_TWIN.md`](DEMAND_MANAGEMENT_TWIN.md)
