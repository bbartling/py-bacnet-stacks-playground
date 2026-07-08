"""Tests for engineer auth and package lock."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from engineer_auth import can_edit, is_locked, lock_package, login, logout


def test_can_edit_when_unlocked():
    assert can_edit({}) is True


def test_locked_requires_engineer():
    sess = {"package_locked": True}
    assert can_edit(sess) is False
    login(sess, "vibe-coder")
    assert can_edit(sess) is True
    logout(sess)
    assert can_edit(sess) is False


def test_lock_package():
    sess: dict = {}
    lock_package(sess)
    assert is_locked(sess) is True
