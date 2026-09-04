"""Battery dispatch solvers (greedy heuristic + cyclic LP bound)."""

from .optimal import cyclic_lp_dispatch, optimality_gap

__all__ = ["cyclic_lp_dispatch", "optimality_gap"]
