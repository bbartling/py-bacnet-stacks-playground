"""Ordering behavior shared by the ECM Easy Buttons UI."""

from __future__ import annotations

from wattlab.ecm.ranking import complexity_sort_key


def test_complexity_sort_key_orders_low_medium_high_then_category_and_id() -> None:
    entries = [
        {"implementation_complexity": "high", "category": "oa", "ecm_id": "ECM-C"},
        {"implementation_complexity": "medium", "category": "z", "ecm_id": "ECM-B"},
        {"implementation_complexity": "low", "category": "z", "ecm_id": "ECM-Z"},
        {"implementation_complexity": "low", "category": "a", "ecm_id": "ECM-A"},
    ]

    assert [entry["ecm_id"] for entry in sorted(entries, key=complexity_sort_key)] == [
        "ECM-A",
        "ECM-Z",
        "ECM-B",
        "ECM-C",
    ]
