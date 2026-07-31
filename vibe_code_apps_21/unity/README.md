# Unity Editor project home (Vibe 21)

**Create the Unity project here — not in `vibe_code_apps_21/` root.**

```text
vibe_code_apps_21/unity/<ProjectName>/   ← e.g. Liberty100 or DemandTwin
  Assets/
  Packages/
  ProjectSettings/
  # Library / Temp / Logs / UserSettings / *.csproj / *.sln are gitignored
```

## Why this folder

| Path | Role |
| --- | --- |
| `assets/twin_b100_ops11/` | Canonical Twin JSON / IDF / EPW (Python + agents) |
| `unity/<ProjectName>/` | Unity Editor project (scenes, materials, WebGL export source) |
| deploy zip / `Builds/` | Generated WebGL only — not the Editor project |

Opening `vibe_code_apps_21/` itself as a Unity project dumps `Library/` next to Python assets and fights git. Keep Editor projects under `unity/`.

## Fresh project (start over)

1. Unity Hub → **New project** (URP recommended) → location  
   `…/py-bacnet-stacks-playground/vibe_code_apps_21/unity/Liberty100`
2. Import geometry from  
   `../assets/twin_b100_ops11/unity_geometry.json`  
   (and bind via `unity_twin_manifest.json` — see `vibe21_agent_spec/UNITY_WEBGL_HANDOFF.md`).
3. Commit only `Assets/`, `Packages/`, `ProjectSettings/` (and this tree’s tracked files).  
   Never commit `Library/`, `Temp/`, `Logs/`, `UserSettings/`, or generated `.csproj` / `.sln`.

`.gitignore` in this folder + root `.gitignore` belt-and-suspenders already exclude Unity junk.
