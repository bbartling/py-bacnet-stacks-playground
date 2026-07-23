#!/usr/bin/env python3
"""Thin wrapper: prefer `wattlab controls-checklist` in tip images.

Copy to $WATTLAB_HOST_WORKSPACE/tools/controls_service_checklist.py if agents
still invoke the historical /data/tools path.
"""
from wattlab.existing_building.controls_checklist import main

if __name__ == "__main__":
    raise SystemExit(main())
