"""Native EnergyPlus runner / validator for Lakeside heating DSM.

Provenance ``ENERGYPLUS_NATIVE_RUN`` is assigned only after fail-closed gates pass.
Electric demand is always Ideal Loads + fixed-COP proxy — never a GSHP plant claim.
"""

from __future__ import annotations

PROXY_FORMULA_VERSION = "ideal_loads_cop_proxy.v1"
PROVENANCE_NATIVE = "ENERGYPLUS_NATIVE_RUN"
DEFAULT_HEAT_COP = 3.5
DEFAULT_COOL_COP = 4.5
EXPECTED_IDF_SHA256 = "23EBE5207BC6D30A64C50EF969281F243719DBB720E36F0A8BC0108D7F5EA83B"
EXPECTED_EPW_SHA256 = "DBFD1148A6627B53A1C6D5BA5E7B5FE7C4733FBE03865873D707D04EE22608D3"
DEFAULT_EPLUS_EXE = r"C:\EnergyPlusV26-1-0\energyplus.exe"

__all__ = [
    "PROXY_FORMULA_VERSION",
    "PROVENANCE_NATIVE",
    "DEFAULT_HEAT_COP",
    "DEFAULT_COOL_COP",
    "EXPECTED_IDF_SHA256",
    "EXPECTED_EPW_SHA256",
    "DEFAULT_EPLUS_EXE",
]
