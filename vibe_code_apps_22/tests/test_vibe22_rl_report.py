"""Guard: year2xsyn report must not wipe unique-100 plots/rl_report."""
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
_SRC = _APP / "scripts" / "vibe22_rl.py"


def test_year2xsyn_report_writes_rl_report_year2x():
    text = _SRC.read_text(encoding="utf-8")
    assert "rl_report_year2x" in text
    assert "day_pool.json" in text
    assert "report_only_no_retrain" in text
    camp = text.split("def cmd_campaign")[1].split("def cmd_preflight")[0]
    assert "resolve_a04_and_epw" not in camp
    assert "verify_active_model" in camp
    assert "resolve_site_epw" in camp
