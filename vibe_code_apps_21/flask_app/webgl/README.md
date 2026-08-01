# Unity WebGL build drop folder (Cannon layout)

Filled by:

```powershell
powershell -File tools/build_webgl_pa.ps1
# or Unity menu: Vibe21 → Build WebGL → flask_app/webgl
```

Expected:

```
webgl/
  index.html
  Build/WebGL.*
  TemplateData/
  StreamingAssets/   (optional)
```

`pack_pa_bundle.py` **refuses** to zip without `index.html`.
