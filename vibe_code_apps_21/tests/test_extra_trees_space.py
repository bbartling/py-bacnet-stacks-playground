"""ExtraTrees search space expansions for demand_hourly tune."""

from __future__ import annotations

import sys
from pathlib import Path

_ML = Path(__file__).resolve().parents[1] / "ml"
if str(_ML) not in sys.path:
    sys.path.insert(0, str(_ML))


def test_extra_trees_space_has_expanded_keys():
    from tune_demand_hourly import SEARCH_SPACES

    proto, space = SEARCH_SPACES["extra_trees"]
    assert proto.__class__.__name__ == "ExtraTreesRegressor"
    for key in (
        "n_estimators",
        "max_depth",
        "min_samples_leaf",
        "min_samples_split",
        "max_features",
        "max_leaf_nodes",
        "bootstrap",
    ):
        assert key in space, f"missing {key}"
    assert 400 in space["n_estimators"]
    assert "sqrt" in space["max_features"]
    assert False in space["bootstrap"] and True in space["bootstrap"]
