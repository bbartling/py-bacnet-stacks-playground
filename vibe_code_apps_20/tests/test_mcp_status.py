"""Honest EnergyPlus MCP capability status (no Docker pull required)."""

from __future__ import annotations

from wattlab.energyplus.mcp import capability_status, mcp_vendor_ready


def test_capability_status_shape():
    status = capability_status(probe_docker=False)
    assert "image" in status
    assert "vendor_present" in status
    assert status["vendor_present"] is mcp_vendor_ready()
    assert status["capability"] in {
        "full_mcp_available",
        "simulate_only",
        "vendor_only_no_image",
        "unavailable",
    }
    assert "apihelper_note" in status
    assert "pyenergyplus" in status["apihelper_note"].lower() or "Runtime" in status["apihelper_note"]
    # Without docker probe, image_present stays False
    assert status["image_present"] is False
    assert status["simulate_via_docker"] is False
