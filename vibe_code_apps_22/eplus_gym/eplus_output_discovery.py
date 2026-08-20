"""Parse EnergyPlus RDD names. Never guess Output:Variable identifiers."""
from __future__ import annotations

import re

RDD_LINE = re.compile(
    r"^\s*Output:Variable\s*,\s*([^,]*),\s*([^,]+)\s*,",
    re.I,
)

WANTED_DIAGNOSTIC_VARIABLES = (
    "Heating Coil Air Mass Flow Rate",
    "Heating Coil Water Mass Flow Rate",
    "Heating Coil Part Load Ratio",
    "Heating Coil Runtime Fraction",
    "Heating Coil Electric Power",
    "Heating Coil Electricity Rate",
    "Heating Coil Heating Rate",
    "Heating Coil Source Side Heat Transfer Rate",
    "Heating Coil Source Side Mass Flow Rate",
    "Cooling Coil Air Mass Flow Rate",
    "Cooling Coil Water Mass Flow Rate",
    "Cooling Coil Part Load Ratio",
    "Cooling Coil Runtime Fraction",
    "Cooling Coil Electric Power",
    "Cooling Coil Electricity Rate",
    "Cooling Coil Total Cooling Rate",
    "Cooling Coil Source Side Heat Transfer Rate",
    "Fan Air Mass Flow Rate",
    "Fan Electricity Rate",
    "Fan Electric Power",
    "Pump Electricity Rate",
    "Pump Electric Power",
    "Pump Mass Flow Rate",
    "System Node Temperature",
    "System Node Mass Flow Rate",
    "Zone Predicted Sensible Load to Setpoint Heat Transfer Rate",
    "Zone Thermostat Heating Setpoint",
    "Zone Thermostat Heating Setpoint Temperature",
    "Zone Mean Air Temperature",
)


def parse_rdd_variable_names(rdd_text: str) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for line in rdd_text.splitlines():
        m = RDD_LINE.match(line)
        if not m:
            continue
        name = m.group(2).strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def select_confirmed_variables(rdd_names: list[str] | set[str], wanted: list[str] | tuple[str, ...]) -> list[str]:
    available = set(rdd_names)
    return [name for name in wanted if name in available]


def confirmed_diagnostic_variables(rdd_text: str) -> list[str]:
    return select_confirmed_variables(parse_rdd_variable_names(rdd_text), WANTED_DIAGNOSTIC_VARIABLES)
