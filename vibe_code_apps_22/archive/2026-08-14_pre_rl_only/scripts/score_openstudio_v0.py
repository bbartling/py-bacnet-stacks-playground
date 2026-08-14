#!/usr/bin/env python
"""Score eplus/runs/openstudio_v0/sim vs utility monthly bills."""
from __future__ import annotations


import sys
from pathlib import Path as _PathForLakeside

_APP = _PathForLakeside(__file__).resolve().parents[1]
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))
from lakeside.paths import (  # noqa: E402
    BUILDING_LABEL,
    CAMPUS_ID,
    REGION_LABEL,
    app_root,
    clean_data_building_dir,
    eplus_dir,
    packages_dir,
    reports_dir,
    site_root,
    utilities_dir,
)
from lakeside.paths import BUILDING_ID as _LAKESIDE_BUILDING_ID  # noqa: E402
from lakeside.paths import SITE_REF as _LAKESIDE_SITE_REF  # noqa: E402
APP = app_root()
import json
import os
import sys
from pathlib import Path

ROOT = site_root()
sys.path.insert(0, str(APP / "scripts"))
from eplus_score_run import score_run  # noqa: E402

OBS = ROOT / "reports" / "eplus" / "observed_monthly_utility.csv"
SIM = ROOT / "eplus" / "runs" / "openstudio_v0" / "sim"
OUT = ROOT / "eplus" / "scorecards" / "openstudio_v0_scorecard.json"


def main() -> int:
    os.environ["EPLUS_OBS_CSV"] = str(OBS)
    if not OBS.is_file():
        raise SystemExit(f"missing {OBS}")
    if not SIM.is_dir():
        raise SystemExit(f"missing sim dir {SIM}")
    sc = score_run(SIM, iter_id="openstudio_v0")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(sc, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": sc.get("gl14_status"),
                "gl14": sc.get("gl14"),
                "scorecard": str(OUT),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
