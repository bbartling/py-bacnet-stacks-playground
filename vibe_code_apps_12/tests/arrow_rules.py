"""Shared Arrow rule snippets for VIBE12 tests (open-fdd 3.x)."""

ARROW_OOB = """from open_fdd.arrow_runtime.cookbook import oob_mask


def apply_faults_arrow(table, cfg, context=None):
    return oob_mask(table, cfg, col="temp")
"""

ARROW_FALSE = """import pyarrow as pa


def apply_faults_arrow(table, cfg, context=None):
    return pa.array([False] * table.num_rows, type=pa.bool_())
"""

ARROW_SAT_RAT_SPREAD = """import pyarrow as pa
import pyarrow.compute as pc


def apply_faults_arrow(table, cfg, context=None):
    sat = pc.cast(table["SAT"], pa.float64())
    rat = pc.cast(table["RAT"], pa.float64())
    spread = pc.abs(pc.subtract(sat, rat))
    return pc.greater(spread, cfg["max_spread"])
"""
