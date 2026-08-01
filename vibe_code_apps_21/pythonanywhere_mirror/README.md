# PythonAnywhere mirror (Vibe21 DM Twin)

Matches **CannonPhysicsSim** `pythonanywhere_flask`: flat `flask_app.py`,
`webgl/` at app root, WSGI `from flask_app import app as application`.

Live package code stays in `vibe_code_apps_21/flask_app/` locally.
The turnkey zip **renames** that package to `twin_api/` so it does not clash
with the flat `flask_app.py` module name on mysite.

## Turnkey zip (includes WebGL player)

```powershell
cd vibe_code_apps_21
powershell -File tools/build_webgl_pa.ps1   # Unity WebGL → flask_app/webgl → pack
# or, if webgl/ already built:
python tools/pack_pa_bundle.py             # fails if webgl/index.html missing
```

## Extract into mysite (not `~`)

```bash
unzip -o vibe21_pa_bundle.zip -d /home/bensApi/mysite
```

Zip contents:

```
mysite/
  flask_app.py          # flat WSGI entry (Cannon-identical import)
  requirements.txt
  twin_api/             # app + models + static
  ml/
  webgl/                # Unity twin WebGL when present
  README_PA.md
```

## WSGI (same as tank-war)

```python
import sys

project_home = "/home/bensApi/mysite"
if project_home not in sys.path:
    sys.path = [project_home] + sys.path

from flask_app import app as application
```

## Virtualenv

Install with the **Web tab** virtualenv pip (not bare `pip` → `~/.local`):

```bash
workon YOUR_VENV
pip install -r ~/mysite/requirements.txt
```

Then Reload. Public URL: `https://bensapi.pythonanywhere.com/`  
(not the Files browser URL under `pythonanywhere.com/user/.../files/...`).

## Static maps (optional)

| URL | Directory |
|-----|-----------|
| `/Build/` | `/home/bensApi/mysite/webgl/Build` |
| `/TemplateData/` | `/home/bensApi/mysite/webgl/TemplateData` |

See `../vibe21_agent_spec/PYTHONANYWHERE_DEPLOYMENT.md`.
