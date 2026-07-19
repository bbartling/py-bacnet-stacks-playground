"""Tests for eplusout.err parsing (warnings / severe / fatal triage)."""

from __future__ import annotations

from pathlib import Path

from wattlab.energyplus.err import parse_err_file, parse_err_text

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_success_with_warnings() -> None:
    out = parse_err_file(FIXTURES / "err_success_warnings.err")
    assert out["warnings"] == 2
    assert out["severe"] == 0
    assert out["fatal"] == 0
    assert out["completed_successfully"] is True
    assert out["results_suspect"] is False
    assert out["ok"] is True
    assert out["missing"] is False


def test_severe_but_completed_marks_results_suspect() -> None:
    out = parse_err_file(FIXTURES / "err_severe_completed.err")
    assert out["warnings"] == 1
    assert out["severe"] == 2
    assert out["fatal"] == 0
    assert out["completed_successfully"] is True
    assert out["results_suspect"] is True
    # Continuation lines fold into the first severe message.
    assert "Temperature (low) out of bounds" in out["severe_messages"][0]
    assert "Zone air temperature = -87.55" in out["severe_messages"][0]
    assert out["severe_messages"][1].startswith("Plant temperatures are getting")


def test_fatal_terminated() -> None:
    out = parse_err_file(FIXTURES / "err_fatal.err")
    assert out["severe"] == 1
    assert out["fatal"] == 1
    assert out["completed_successfully"] is False
    assert out["terminated"] is True
    assert out["results_suspect"] is True
    assert out["ok"] is False
    assert "Errors occurred on processing input file" in out["fatal_messages"][0]


def test_missing_file_is_not_ok(tmp_path: Path) -> None:
    out = parse_err_file(tmp_path / "does_not_exist.err")
    assert out["missing"] is True
    assert out["ok"] is False
    assert out["results_suspect"] is True


def test_empty_text_is_incomplete() -> None:
    out = parse_err_text("")
    assert out["completed_successfully"] is False
    assert out["ok"] is False
