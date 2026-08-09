"""Each multi-output family fits tiny synthetic data and predicts (n, 7)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP / "ml"))

from multioutput_families import lean_family_protos, wrap_family  # noqa: E402


def test_all_lean_families_predict_shape():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(40, 8))
    Y = rng.normal(size=(40, 7))
    protos = lean_family_protos(n_jobs=1)
    for name, proto in protos.items():
        m = wrap_family(name, proto, n_jobs=1)
        m.fit(X, Y)
        pred = np.asarray(m.predict(X[:5]), dtype=float)
        assert pred.shape == (5, 7), f"{name} got {pred.shape}"
