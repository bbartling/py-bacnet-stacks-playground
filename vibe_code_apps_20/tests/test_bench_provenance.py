"""Clean-room provenance contract for public calculator records."""

from wattlab.bench.provenance import load_provenance


CALCULATORS = {
    "scheduling_fan_bins",
    "scheduling_cooling_bins",
    "scheduling_heating_bins",
    "oad_unoccupied_closed",
    "dcv_bins",
    "static_pressure_reset",
    "dat_reset_bins",
    "hydronic_reset_bins",
    "dewpoint_economizer",
}

EXPECTED_STATEMENT = (
    "Independently implemented from standard HVAC engineering relationships "
    "and validated numerically against private legacy calculations. The private "
    "workbook is not distributed, required, or embedded."
)


def test_each_esco_calculator_has_clean_room_provenance() -> None:
    records = load_provenance()

    assert set(records) == CALCULATORS
    assert all(record["statement"] == EXPECTED_STATEMENT for record in records.values())
    assert all(record["runtime_dependency"] is False for record in records.values())
