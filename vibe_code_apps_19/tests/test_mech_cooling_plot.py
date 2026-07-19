"""Plotly mechanical-cooling OAT histogram: stacked devices + aggregate lines."""

from __future__ import annotations

import pandas as pd
import pytest

from app.charts import mech_cooling_oat_histogram, mech_cooling_runtime_message


def _bin_row(
    *,
    equipment_id: str,
    source: str,
    source_kind: str,
    series_kind: str,
    series_id: str,
    bin_start: int,
    hours: float,
    equipment_type: str = "CHW_PLANT",
    cooling_technology: str = "chilled_water_plant",
    proof_role: str = "chiller-status",
    proof_quality: str = "direct",
    device_count: int = 1,
    coverage_pct: float = 100.0,
    valid_elapsed_hours: float = 4.0,
) -> dict:
    return {
        "equipment_id": equipment_id,
        "source": source,
        "source_kind": source_kind,
        "series_kind": series_kind,
        "series_id": series_id,
        "bin_start": bin_start,
        "bin_label": f"{bin_start}–{bin_start + 5}",
        "hours": hours,
        "runtime_hours": hours,
        "valid_elapsed_hours": valid_elapsed_hours,
        "coverage_pct": coverage_pct,
        "equipment_type": equipment_type,
        "cooling_technology": cooling_technology,
        "proof_role": proof_role,
        "proof_quality": proof_quality,
        "device_count": device_count,
    }


def one_device_rows() -> pd.DataFrame:
    """One individual device whose hours equal both aggregate series."""
    return pd.DataFrame(
        [
            _bin_row(
                equipment_id="CHILLER_2",
                source="CHILLER_2 (chiller-status)",
                source_kind="chiller-status",
                series_kind="individual_device",
                series_id="CHILLER_2",
                bin_start=70,
                hours=2.0,
            ),
            _bin_row(
                equipment_id="ALL",
                source="All mech cooling (total) — 1 device(s)",
                source_kind="total",
                series_kind="aggregate_device_hours",
                series_id="aggregate_device_hours",
                bin_start=70,
                hours=2.0,
                equipment_type="",
                cooling_technology="",
                proof_role="",
                proof_quality="",
                device_count=1,
            ),
            _bin_row(
                equipment_id="ACTIVE",
                source="Any compressor active",
                source_kind="active",
                series_kind="aggregate_active_hours",
                series_id="aggregate_active_hours",
                bin_start=70,
                hours=2.0,
                equipment_type="",
                cooling_technology="",
                proof_role="",
                proof_quality="",
                device_count=1,
            ),
        ]
    )


def two_device_equal_aggregate_rows() -> pd.DataFrame:
    """Two devices in one bin; aggregates equal the stacked sum (no dedupe)."""
    return pd.DataFrame(
        [
            _bin_row(
                equipment_id="CHILLER_1",
                source="CHILLER_1 (chiller-status)",
                source_kind="chiller-status",
                series_kind="individual_device",
                series_id="CHILLER_1",
                bin_start=65,
                hours=1.5,
            ),
            _bin_row(
                equipment_id="CHILLER_2",
                source="CHILLER_2 (chiller-status)",
                source_kind="chiller-status",
                series_kind="individual_device",
                series_id="CHILLER_2",
                bin_start=65,
                hours=1.5,
            ),
            _bin_row(
                equipment_id="ALL",
                source="All mech cooling (total) — 2 device(s)",
                source_kind="total",
                series_kind="aggregate_device_hours",
                series_id="aggregate_device_hours",
                bin_start=65,
                hours=3.0,
                equipment_type="",
                cooling_technology="",
                proof_role="",
                proof_quality="",
                device_count=2,
            ),
            _bin_row(
                equipment_id="ACTIVE",
                source="Any compressor active",
                source_kind="active",
                series_kind="aggregate_active_hours",
                series_id="aggregate_active_hours",
                bin_start=65,
                hours=1.5,
                equipment_type="",
                cooling_technology="",
                proof_role="",
                proof_quality="",
                device_count=2,
            ),
        ]
    )


def test_empty_bins_return_none():
    assert mech_cooling_oat_histogram(pd.DataFrame()) is None
    assert mech_cooling_oat_histogram(None) is None


def test_one_device_figure_keeps_three_semantic_traces():
    fig = mech_cooling_oat_histogram(one_device_rows())
    assert fig is not None
    assert [trace.name for trace in fig.data] == [
        "CHILLER_2",
        "Total compressor device-hours",
        "Any compressor active",
    ]
    assert fig.data[0].type == "bar"
    assert fig.data[1].type == "scatter"
    assert fig.data[2].type == "scatter"
    assert fig.layout.barmode == "stack"
    assert all(trace.showlegend is not False for trace in fig.data)


def test_aggregate_traces_use_line_modes_outside_stack():
    fig = mech_cooling_oat_histogram(one_device_rows())
    assert fig is not None
    device_hours, active_hours = fig.data[1], fig.data[2]
    assert device_hours.mode == "lines+markers"
    assert active_hours.mode == "lines+markers"
    assert active_hours.line.dash in {"dash", "dashed"}
    assert device_hours.legendgroup == "aggregate_device_hours"
    assert active_hours.legendgroup == "aggregate_active_hours"
    assert fig.data[0].legendgroup == "CHILLER_2"


def test_equal_y_values_are_not_deduplicated():
    fig = mech_cooling_oat_histogram(one_device_rows())
    assert fig is not None
    ys = [list(trace.y) for trace in fig.data]
    assert ys[0] == [2.0]
    assert ys[1] == [2.0]
    assert ys[2] == [2.0]
    names = [trace.name for trace in fig.data]
    assert len(names) == len(set(names))


def test_two_device_stack_keeps_both_aggregate_lines():
    fig = mech_cooling_oat_histogram(two_device_equal_aggregate_rows())
    assert fig is not None
    assert [t.type for t in fig.data] == ["bar", "bar", "scatter", "scatter"]
    assert [t.name for t in fig.data] == [
        "CHILLER_1",
        "CHILLER_2",
        "Total compressor device-hours",
        "Any compressor active",
    ]
    assert list(fig.data[2].y) == [3.0]
    assert list(fig.data[3].y) == [1.5]


def _hover_blob(trace) -> str:
    parts = [str(trace.hovertemplate or "")]
    if getattr(trace, "customdata", None) is not None:
        parts.append(str(trace.customdata))
    if getattr(trace, "hovertext", None) is not None:
        parts.append(str(trace.hovertext))
    return " ".join(parts).lower()


@pytest.mark.parametrize(
    "field",
    [
        "proof",
        "coverage",
        "device",
        "runtime",
        "equipment",
        "cooling",
        "oat",
    ],
)
def test_hover_includes_proof_count_coverage_metadata(field: str):
    fig = mech_cooling_oat_histogram(one_device_rows())
    assert fig is not None
    blob = " ".join(_hover_blob(t) for t in fig.data)
    assert field in blob


def test_runtime_message_one_active_device():
    coverage = pd.DataFrame(
        [
            {
                "equipment_id": "CHILLER_2",
                "included": True,
                "eligibility_state": "eligible_with_runtime",
                "activity_state": "active",
                "runtime_hours": 2.0,
            },
            {
                "equipment_id": "CHILLER_1",
                "included": True,
                "eligibility_state": "eligible_no_runtime",
                "activity_state": "inactive",
                "runtime_hours": 0.0,
            },
        ]
    )
    msg = mech_cooling_runtime_message(coverage)
    assert msg is not None
    assert "Only CHILLER_2 had observed compressor runtime during this period." in msg
    assert "Total compressor device-hours therefore equal CHILLER_2 runtime." in msg


def test_runtime_message_absent_when_multiple_active():
    coverage = pd.DataFrame(
        [
            {
                "equipment_id": "CHILLER_1",
                "included": True,
                "eligibility_state": "eligible_with_runtime",
                "activity_state": "active",
                "runtime_hours": 1.0,
            },
            {
                "equipment_id": "CHILLER_2",
                "included": True,
                "eligibility_state": "eligible_with_runtime",
                "activity_state": "active",
                "runtime_hours": 1.0,
            },
        ]
    )
    assert mech_cooling_runtime_message(coverage) is None


def test_runtime_message_absent_when_no_runtime():
    coverage = pd.DataFrame(
        [
            {
                "equipment_id": "CHILLER_1",
                "included": True,
                "eligibility_state": "eligible_no_runtime",
                "activity_state": "inactive",
                "runtime_hours": 0.0,
            }
        ]
    )
    assert mech_cooling_runtime_message(coverage) is None
