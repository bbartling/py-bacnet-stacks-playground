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
import openstudio

print("OS", openstudio.openStudioVersion())
print("E+", openstudio.energyPlusVersion())
m = openstudio.model.Model()
z = openstudio.model.ThermalZone(m)
z.setName("TestZone")
print("zone", z.nameString(), "spaces", len(list(m.getSpaces())))
