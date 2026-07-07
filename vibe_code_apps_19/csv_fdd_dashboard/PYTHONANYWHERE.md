# PythonAnywhere deploy — Building 100 RCx Dashboard

Same workflow as Unity WebGL → zip → upload → Flask serves the build.

| Unity WebGL | This dashboard |
|-------------|----------------|
| WebGL Build/ folder | `site/` (pre-baked HTML charts) |
| Minimal Flask/static server | `app.py` + `wsgi.py` |
| Upload zip to PythonAnywhere | `building100_pa_deploy.zip` |

---

## 1. Build locally (your machine)

```bash
cd vibe_code_apps_19/csv_fdd_dashboard
pip install -r requirements-dev.txt

# Optional: tune charts + write notes locally
set DASHBOARD_MODE=full
python app.py
# Open http://127.0.0.1:5000/index.html — tune sliders, add notes, save

# Build the PA zip (bakes charts into site/, includes notes)
python build_pa_deploy.py --from-session
```

Output: **`building100_pa_deploy.zip`**

---

## 2. Upload to PythonAnywhere

1. Log in at [pythonanywhere.com](https://www.pythonanywhere.com)
2. **Files** → upload `building100_pa_deploy.zip`
3. Open a **Bash console** and extract:

```bash
cd ~
unzip -o building100_pa_deploy.zip -d building100_dashboard
cd building100_dashboard
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

4. **Web** tab → **Add a new web app** → Manual configuration → Python 3.10
5. Edit the **WSGI configuration file** (link on Web tab). Replace contents with:

```python
import sys
path = '/home/YOURUSERNAME/building100_dashboard'
if path not in sys.path:
    sys.path.insert(0, path)

import os
os.environ['DASHBOARD_MODE'] = 'deploy'
os.environ['ANALYST_ENABLED'] = '1'   # 0 = view-only, no note editing

from app import application
```

Replace `YOURUSERNAME` with your PythonAnywhere username.

6. Set **Virtualenv** on the Web tab to:
   `/home/YOURUSERNAME/building100_dashboard/venv`

7. Click **Reload** on the Web tab.

8. Visit `https://YOURUSERNAME.pythonanywhere.com/index.html`

---

## Modes on PythonAnywhere

| Env var | Value | Behavior |
|---------|-------|----------|
| `DASHBOARD_MODE` | `deploy` | Serve pre-built `site/` charts (required on PA) |
| `ANALYST_ENABLED` | `1` | Show notes textarea + Save (charts still read-only) |
| `ANALYST_ENABLED` | `0` | View-only for clients — no edit UI |

Notes are saved to `data/analyst_notes.json` on the PA server. **Charts do not recompute on PA** — rebuild the zip locally and re-upload to update charts (same as re-exporting a WebGL build).

---

## 3. Update after local changes

```bash
# Local: re-tune, re-export
python build_pa_deploy.py --from-session

# Re-upload zip to PA, extract over existing folder, Reload web app
```

---

## Troubleshooting

- **Blank charts:** confirm `site/plotly.min.js` exists after extract
- **404 on pages:** extract zip so `site/index.html` is at `~/building100_dashboard/site/index.html`
- **500 error:** check error log on Web tab; usually wrong virtualenv or WSGI path
- **Notes not saving:** set `ANALYST_ENABLED=1`; check `data/` is writable on PA
