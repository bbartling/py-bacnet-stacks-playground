"""Engineering adapters — thin bridges to Open-FDD / other shared libs.

Generic ECM spreadsheet math lives on PyPI ``open-fdd``
(``open_fdd.ecm_engineering``). WattLab keeps EnergyPlus / Studio / catalog
IDs here and calls Open-FDD through :mod:`wattlab.engineering.openfdd_ecm`.
"""

from __future__ import annotations

from .openfdd_ecm import calculate, list_calculators, openfdd_available

__all__ = [
    "calculate",
    "list_calculators",
    "openfdd_available",
]
