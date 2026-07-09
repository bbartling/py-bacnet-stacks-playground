"""Tests for notes blog storage and display-layer units."""

from notes_store import add_post, delete_post, migrate_notes, posts_for_page
from units import fmt_temp, f_to_c, set_display_units, substitute_temp_text


def test_migrate_legacy_string_note():
    raw = {"index": "hello world"}
    out = migrate_notes(raw)
    assert len(out["index"]) == 1
    assert out["index"][0]["text"] == "hello world"


def test_add_and_delete_post():
    notes = {}
    add_post(notes, "zones", "first finding", author="Ben")
    assert len(posts_for_page(notes, "zones")) == 1
    pid = notes["zones"][0]["id"]
    assert delete_post(notes, "zones", pid)
    assert posts_for_page(notes, "zones") == []


def test_display_temp_metric():
    set_display_units("metric")
    assert "°C" in fmt_temp(72)
    assert abs(f_to_c(32)) < 0.01
    text = substitute_temp_text("OAT < 72°F")
    assert "°C" in text
    set_display_units("imperial")
