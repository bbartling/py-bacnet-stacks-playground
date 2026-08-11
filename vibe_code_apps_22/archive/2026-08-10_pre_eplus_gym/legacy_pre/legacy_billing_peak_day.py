"""ARCHIVED — do not import. Legacy playground billing peak.

Bug: existing_billing_peak_kw = nanmax(actual_day) suppresses demand-charge
credit for strategies that cut the day's historical peak.
"""
import numpy as np


def existing_billing_peak_from_actual_day(kw_actual) -> float:
    return float(np.nanmax(kw_actual))
