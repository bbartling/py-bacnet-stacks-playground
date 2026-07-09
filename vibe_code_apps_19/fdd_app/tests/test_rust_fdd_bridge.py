"""Tests for local Rust fdd_cli bridge."""

from __future__ import annotations

import rust_fdd_bridge as rfb


def test_rust_fdd_bridge_status_shape():
    st = rfb.status()
    assert "available" in st
    assert "rust_root" in st
    assert "rules_dir" in st
