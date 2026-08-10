"""CLI training is allowed for the parallel arm launcher.

Preferred::

    python scripts/train_four_arms.py --profile full_evaluation

Set ``VIBE22_ALLOW_CLI_TRAIN=1`` (the launcher sets this automatically).
Notebooks are results viewers only.
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
        f"REFUSED: {component} — use the parallel trainer (not an in-kernel notebook fit).\n"
        f"  cd vibe_code_apps_22\n"
        f"  python scripts/train_four_arms.py --profile full_evaluation\n"
        f"  # then open {notebook} as a results viewer\n"
        f"Or set VIBE22_ALLOW_CLI_TRAIN=1 for legacy single-arm CLIs.",
        file=sys.stderr,
    )
    return 2
