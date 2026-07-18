"""WattLab — EnergyPlus digital-twin toolkit for the vibe19 → ESCO workflow.

Subpackages:
- ``wattlab.config`` / ``wattlab.defaults`` — paths, pins, responsive defaults
- ``wattlab.seed`` — vibe19 WattLab dump loader + gap report
- ``wattlab.weather`` — AMY EPW builder + Weather-Man OAT bin tables
- ``wattlab.energyplus`` — Docker/MCP runners, results parsing, IDF patches
- ``wattlab.measures`` — ECM catalog (good/better/best measure sets)
- ``wattlab.bench`` — deterministic proxy + ESCO bin-method calculators
- ``wattlab.easy_button`` / ``wattlab.calibrate`` / ``wattlab.bridge`` — workflows
"""

from __future__ import annotations

__version__ = "0.2.0"
