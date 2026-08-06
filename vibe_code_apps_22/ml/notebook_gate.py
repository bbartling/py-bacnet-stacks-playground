"""Force hybrid model training through notebooks (human SoT).

CLI entry points refuse unless ``VIBE22_ALLOW_CLI_TRAIN=1`` (emergency only).
"""
from __future__ import annotations

import os
import sys

SKLEARN_NOTEBOOK = "notebooks/lakeside_heating_dsm_sklearn.ipynb"
TORCH_NOTEBOOK = "notebooks/lakeside_heating_dsm_torch.ipynb"


def cli_train_allowed() -> bool:
    return os.environ.get("VIBE22_ALLOW_CLI_TRAIN", "").strip() == "1"


def refuse_cli_train(component: str, *, notebook: str = SKLEARN_NOTEBOOK) -> int:
    """Print refuse message and return exit code 2."""
    print(
        f"REFUSED: {component} training must run via the notebook (human SoT).\n"
        f"  Open and Run All: vibe_code_apps_22/{notebook}\n"
        f"Emergency CLI only: set VIBE22_ALLOW_CLI_TRAIN=1\n"
        "See vibe22_agent_spec/HEATING_DSM.md",
        file=sys.stderr,
    )
    return 2
