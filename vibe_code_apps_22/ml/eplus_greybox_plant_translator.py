"""Deprecated shim — use eplus_proxy_corrector_diagnostic.

Kept so older imports of eplus_greybox_plant_translator continue to resolve.
"""
from eplus_proxy_corrector_diagnostic import *  # noqa: F403
from eplus_proxy_corrector_diagnostic import (  # noqa: F401
    FAMILY,
    FEATURE_COLS,
    PRODUCT_CLAIM,
    build_greybox_frame,
    run_greybox_bakeoff,
    run_proxy_corrector_bakeoff,
    write_greybox_report,
)
