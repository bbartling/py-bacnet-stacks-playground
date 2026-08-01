# Unity WebGL build drop folder

Export the Liberty100Twin WebGL player here so Flask can serve it:

```
flask_app/webgl/
  index.html
  Build/
  TemplateData/
  StreamingAssets/   (if used)
```

Local:

```bash
cd vibe_code_apps_21
python -m flask_app   # :5050 — / serves WebGL when present; /api/v1/* always
```

PythonAnywhere: map `/Build/` and `/TemplateData/` to this folder (see `vibe21_agent_spec/PYTHONANYWHERE_DEPLOYMENT.md` and `pythonanywhere_mirror/`).

Until a build is present, `GET /` returns a JSON stub pointing at the API.
