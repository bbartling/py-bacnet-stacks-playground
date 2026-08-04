"""Thin launcher — runs site-workspace utility GL14 campaign.

Preferred:
  cd $env:VIBE23_CREEKSIDE_ROOT
  python -u scripts\\eplus_campaign_utility.py

This copy is documentation/backup; full `eplus_campaign.apply_knobs` + IDF/AMY
live under sp_creekside.
"""
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

root = Path(os.environ.get("VIBE23_CREEKSIDE_ROOT", r"C:\Users\ben\OneDrive\Desktop\testing\sp_creekside"))
script = root / "scripts" / "eplus_campaign_utility.py"
if not script.is_file():
    print(f"missing {script}; set VIBE23_CREEKSIDE_ROOT", file=sys.stderr)
    raise SystemExit(2)
# Prefer site script (may be newer than this mirror)
sys.argv[0] = str(script)
os.chdir(root)
runpy.run_path(str(script), run_name="__main__")
