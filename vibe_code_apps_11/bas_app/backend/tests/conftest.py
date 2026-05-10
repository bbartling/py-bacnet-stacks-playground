from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.audit import clear_events
from app.alarms import reset_alarm_state
from app.commands import clear_command_states


@pytest.fixture(autouse=True)
def reset_audit_events():
    clear_events()
    clear_command_states()
    reset_alarm_state()
    yield
    clear_events()
    clear_command_states()
    reset_alarm_state()
