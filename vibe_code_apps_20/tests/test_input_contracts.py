"""Contract tests for wattlab.contracts (Task 1: weather/utility/scenario inputs).

TDD: these tests were written before wattlab/contracts.py existed and define
the validation behavior for WeatherRequest, WeatherDatasetMeta,
UtilityBillRecord, UtilityDataset, and RetrofitScenario.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from wattlab.contracts import (
    EPW_REQUIRED_VARIABLES,
    RetrofitScenario,
    UtilityBillRecord,
    UtilityDataset,
    WeatherDatasetMeta,
    WeatherRequest,
)


# ---------------------------------------------------------------------------
# WeatherRequest
# ---------------------------------------------------------------------------


def _weather_request(**overrides):
    kwargs = dict(
        latitude=42.33,
        longitude=-83.05,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
    )
    kwargs.update(overrides)
    return WeatherRequest(**kwargs)


class TestWeatherRequest:
    def test_valid_request(self):
        req = _weather_request()
        assert req.timezone == "UTC"
        assert EPW_REQUIRED_VARIABLES <= set(req.variables)

    @pytest.mark.parametrize("lat", [-90.1, 90.1, 91, -400])
    def test_latitude_out_of_range_rejected(self, lat):
        with pytest.raises(ValidationError):
            _weather_request(latitude=lat)

    @pytest.mark.parametrize("lat", [-90, 90, 0.0])
    def test_latitude_boundaries_accepted(self, lat):
        assert _weather_request(latitude=lat).latitude == lat

    @pytest.mark.parametrize("lon", [-180.1, 180.1, 181, 720])
    def test_longitude_out_of_range_rejected(self, lon):
        with pytest.raises(ValidationError):
            _weather_request(longitude=lon)

    @pytest.mark.parametrize("lon", [-180, 180, 0.0])
    def test_longitude_boundaries_accepted(self, lon):
        assert _weather_request(longitude=lon).longitude == lon

    def test_start_after_end_rejected(self):
        with pytest.raises(ValidationError, match="start_date"):
            _weather_request(
                start_date=date(2025, 6, 1), end_date=date(2025, 5, 31)
            )

    def test_start_equal_end_accepted(self):
        req = _weather_request(
            start_date=date(2025, 7, 4), end_date=date(2025, 7, 4)
        )
        assert req.start_date == req.end_date

    def test_non_utc_timezone_rejected(self):
        with pytest.raises(ValidationError, match="UTC"):
            _weather_request(timezone="America/Detroit")

    def test_variables_missing_epw_essentials_rejected(self):
        with pytest.raises(ValidationError, match="EPW"):
            _weather_request(variables=["temperature_2m"])

    def test_extra_variables_beyond_epw_set_accepted(self):
        extra = sorted(EPW_REQUIRED_VARIABLES) + ["precipitation"]
        req = _weather_request(variables=extra)
        assert "precipitation" in req.variables

    def test_duplicate_variables_are_deduplicated(self):
        variables = sorted(EPW_REQUIRED_VARIABLES)
        req = _weather_request(variables=variables + [variables[0]])
        assert req.variables == variables

    def test_allow_partial_defaults_to_false(self):
        assert _weather_request().allow_partial is False

    def test_allow_partial_true_accepted(self):
        assert _weather_request(allow_partial=True).allow_partial is True

    def test_allow_partial_must_be_boolean(self):
        with pytest.raises(ValidationError):
            _weather_request(allow_partial="yes please")


# ---------------------------------------------------------------------------
# WeatherDatasetMeta
# ---------------------------------------------------------------------------


def _weather_meta(**overrides):
    kwargs = dict(
        source="open-meteo-archive",
        latitude=42.33,
        longitude=-83.05,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        variables=sorted(EPW_REQUIRED_VARIABLES),
        rows=8760,
        sha256="a" * 64,
        downloaded_at_utc=datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc),
    )
    kwargs.update(overrides)
    return WeatherDatasetMeta(**kwargs)


class TestWeatherDatasetMeta:
    def test_valid_meta(self):
        meta = _weather_meta()
        assert meta.rows == 8760
        assert meta.timezone == "UTC"

    @pytest.mark.parametrize("rows", [0, -1])
    def test_nonpositive_rows_rejected(self, rows):
        with pytest.raises(ValidationError):
            _weather_meta(rows=rows)

    @pytest.mark.parametrize("sha", ["", "abc", "z" * 64, "A" * 63])
    def test_bad_sha256_rejected(self, sha):
        with pytest.raises(ValidationError):
            _weather_meta(sha256=sha)

    def test_date_order_enforced(self):
        with pytest.raises(ValidationError, match="start_date"):
            _weather_meta(
                start_date=date(2025, 12, 31), end_date=date(2025, 1, 1)
            )

    def test_out_of_range_coordinates_rejected(self):
        with pytest.raises(ValidationError):
            _weather_meta(latitude=99.0)

    def test_non_utc_timezone_rejected(self):
        with pytest.raises(ValidationError, match="UTC"):
            _weather_meta(timezone="America/Detroit")

    def test_variables_missing_epw_essentials_rejected(self):
        with pytest.raises(ValidationError, match="EPW"):
            _weather_meta(variables=["temperature_2m"])

    def test_duplicate_variables_are_deduplicated(self):
        variables = sorted(EPW_REQUIRED_VARIABLES)
        meta = _weather_meta(variables=variables + [variables[0]])
        assert meta.variables == variables

    @pytest.mark.parametrize(
        ("year", "expected_rows"),
        [(2025, 8760), (2024, 8784)],
    )
    def test_full_calendar_year_requires_expected_hour_count(
        self, year, expected_rows
    ):
        with pytest.raises(ValidationError, match=str(expected_rows)):
            _weather_meta(
                start_date=date(year, 1, 1),
                end_date=date(year, 12, 31),
                rows=expected_rows - 1,
            )

    @pytest.mark.parametrize(
        ("year", "rows"),
        [(2025, 8760), (2024, 8784)],
    )
    def test_full_calendar_year_accepts_expected_hour_count(self, year, rows):
        assert (
            _weather_meta(
                start_date=date(year, 1, 1),
                end_date=date(year, 12, 31),
                rows=rows,
            ).rows
            == rows
        )

    def test_partial_span_allows_any_positive_row_count(self):
        meta = _weather_meta(
            start_date=date(2025, 2, 1),
            end_date=date(2025, 2, 2),
            rows=1,
        )
        assert meta.rows == 1


# ---------------------------------------------------------------------------
# UtilityBillRecord
# ---------------------------------------------------------------------------


def _bill(**overrides):
    kwargs = dict(
        month="2025-01",
        fuel="electricity",
        unit="kwh",
        usage=42000.0,
        cost_usd=5100.0,
        demand_kw=180.0,
    )
    kwargs.update(overrides)
    return UtilityBillRecord(**kwargs)


class TestUtilityBillRecord:
    def test_valid_electricity_bill(self):
        bill = _bill()
        assert bill.fuel == "electricity"
        assert bill.unit == "kwh"

    @pytest.mark.parametrize("unit", ["mcf", "therm"])
    def test_valid_gas_units(self, unit):
        bill = _bill(fuel="gas", unit=unit, demand_kw=None)
        assert bill.unit == unit

    @pytest.mark.parametrize(
        "fuel,unit",
        [("electricity", "mcf"), ("electricity", "therm"), ("gas", "kwh")],
    )
    def test_mismatched_fuel_unit_rejected(self, fuel, unit):
        with pytest.raises(ValidationError, match="unit"):
            _bill(fuel=fuel, unit=unit)

    @pytest.mark.parametrize(
        "month",
        ["2025-13", "2025-00", "2025-1", "202501", "01-2025", "abcd-ef", ""],
    )
    def test_bad_month_rejected(self, month):
        with pytest.raises(ValidationError):
            _bill(month=month)

    def test_negative_usage_rejected(self):
        with pytest.raises(ValidationError):
            _bill(usage=-1.0)

    def test_negative_cost_rejected(self):
        with pytest.raises(ValidationError):
            _bill(cost_usd=-0.01)

    def test_negative_demand_rejected(self):
        with pytest.raises(ValidationError):
            _bill(demand_kw=-5.0)

    def test_zero_usage_accepted(self):
        assert _bill(usage=0.0).usage == 0.0

    def test_unknown_fuel_rejected(self):
        with pytest.raises(ValidationError):
            _bill(fuel="steam", unit="mlb")


# ---------------------------------------------------------------------------
# UtilityDataset
# ---------------------------------------------------------------------------


def _months(start_year: int, start_month: int, count: int) -> list[str]:
    out = []
    y, m = start_year, start_month
    for _ in range(count):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out


def _bills(months: list[str], fuel: str = "electricity", unit: str = "kwh"):
    return [
        UtilityBillRecord(
            month=month, fuel=fuel, unit=unit, usage=1000.0 + i, cost_usd=100.0
        )
        for i, month in enumerate(months)
    ]


def _dataset(**overrides):
    kwargs = dict(
        bills=_bills(_months(2025, 1, 12)),
        floor_area_sqft=85000.0,
        provenance="synthetic_rehearsal",
    )
    kwargs.update(overrides)
    return UtilityDataset(**kwargs)


class TestUtilityDataset:
    def test_valid_twelve_consecutive_months(self):
        ds = _dataset()
        assert len(ds.bills) == 12

    def test_year_boundary_span_accepted(self):
        ds = _dataset(bills=_bills(_months(2024, 7, 12)))
        assert ds.bills[0].month == "2024-07"
        assert ds.bills[-1].month == "2025-06"

    def test_unsorted_but_consecutive_months_accepted(self):
        months = _months(2025, 1, 12)
        shuffled = months[6:] + months[:6]
        ds = _dataset(bills=_bills(shuffled))
        assert len(ds.bills) == 12

    @pytest.mark.parametrize("count", [11, 13])
    def test_wrong_bill_count_rejected(self, count):
        with pytest.raises(ValidationError, match="12"):
            _dataset(bills=_bills(_months(2025, 1, count)))

    def test_duplicate_month_rejected(self):
        months = _months(2025, 1, 11) + ["2025-01"]
        with pytest.raises(ValidationError, match="duplicate"):
            _dataset(bills=_bills(months))

    def test_gap_in_months_rejected(self):
        months = _months(2025, 1, 6) + _months(2025, 8, 6)  # skips 2025-07
        with pytest.raises(ValidationError, match="consecutive"):
            _dataset(bills=_bills(months))

    def test_mixed_fuel_rejected(self):
        bills = _bills(_months(2025, 1, 11)) + _bills(
            ["2025-12"], fuel="gas", unit="mcf"
        )
        with pytest.raises(ValidationError, match="fuel"):
            _dataset(bills=bills)

    def test_mixed_units_within_one_fuel_rejected(self):
        bills = _bills(_months(2025, 1, 11), fuel="gas", unit="mcf") + _bills(
            ["2025-12"], fuel="gas", unit="therm"
        )
        with pytest.raises(ValidationError, match="unit"):
            _dataset(bills=bills)

    @pytest.mark.parametrize("area", [0.0, -100.0])
    def test_nonpositive_floor_area_rejected(self, area):
        with pytest.raises(ValidationError):
            _dataset(floor_area_sqft=area)

    @pytest.mark.parametrize("prov", ["actual", "synthetic_rehearsal"])
    def test_known_provenance_accepted(self, prov):
        assert _dataset(provenance=prov).provenance == prov

    def test_unknown_provenance_rejected(self):
        with pytest.raises(ValidationError):
            _dataset(provenance="guessed")


# ---------------------------------------------------------------------------
# RetrofitScenario
# ---------------------------------------------------------------------------


def _scenario(**overrides):
    kwargs = dict(
        name="school_30yr_hydronic",
        measure_ids=["ECM-BOILER-CONDENSING", "ECM-GLAZING-REPLACE"],
        scenario_kind="hydronic_renewal",
        conceptual_surrogate=True,
    )
    kwargs.update(overrides)
    return RetrofitScenario(**kwargs)


class TestRetrofitScenario:
    def test_valid_scenario_defaults_to_30_years(self):
        sc = _scenario()
        assert sc.analysis_years == 30

    def test_electrification_kind_accepted(self):
        sc = _scenario(scenario_kind="electrification")
        assert sc.scenario_kind == "electrification"

    def test_unknown_kind_rejected(self):
        with pytest.raises(ValidationError):
            _scenario(scenario_kind="fusion_reactor")

    def test_empty_measures_rejected(self):
        with pytest.raises(ValidationError):
            _scenario(measure_ids=[])

    def test_duplicate_measures_rejected(self):
        with pytest.raises(ValidationError, match="unique"):
            _scenario(measure_ids=["ECM-A", "ECM-A"])

    def test_blank_measure_id_rejected(self):
        with pytest.raises(ValidationError):
            _scenario(measure_ids=["ECM-A", "  "])

    @pytest.mark.parametrize("years", [0, 41, -5])
    def test_analysis_years_out_of_range_rejected(self, years):
        with pytest.raises(ValidationError):
            _scenario(analysis_years=years)

    @pytest.mark.parametrize("years", [1, 40])
    def test_analysis_years_boundaries_accepted(self, years):
        assert _scenario(analysis_years=years).analysis_years == years

    def test_conceptual_surrogate_is_required(self):
        with pytest.raises(ValidationError, match="conceptual_surrogate"):
            RetrofitScenario(
                name="x",
                measure_ids=["ECM-A"],
                scenario_kind="electrification",
            )

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError):
            _scenario(name="")

    def test_whitespace_only_name_rejected(self):
        with pytest.raises(ValidationError):
            _scenario(name="   ")
