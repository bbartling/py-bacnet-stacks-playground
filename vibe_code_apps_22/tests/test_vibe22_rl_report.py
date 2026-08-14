"""Guard: year2xsyn report must not wipe unique-100 plots/rl_report."""
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
_SRC = _APP / "scripts" / "vibe22_rl.py"


def test_year2xsyn_report_writes_rl_report_year2x():
    text = _SRC.read_text(encoding="utf-8")
    assert "rl_report_year2x" in text
    assert "day_pool.json" in text
    assert "report_only_no_retrain" in text
