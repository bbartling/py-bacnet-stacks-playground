"""ECM-ERV-001: honest HAS_EP_PROTOTYPE stub — not a product cascade patch."""

from __future__ import annotations

import pytest

from wattlab.ecm.catalog import get_ecm
from wattlab.energyplus.patches import (
    apply_patch,
    is_prototype_residual_patch,
    known_patch_names,
    list_prototype_residuals,
    residual_for_measure,
)


def test_erv_residual_is_has_ep_prototype_not_product_patch(tmp_path):
    row = residual_for_measure("ECM-ERV")
    assert row is not None
    assert row["status"] == "HAS_EP_PROTOTYPE"
    assert row["ticket"] == "ECM-ERV-001"
    assert row["stub_patch_name"] == "erv_ahu_prototype"
    assert row["product_patch"] is None
    assert "ECM-AHU-ERV" in row["workbook_aliases"]

    alias = residual_for_measure("ECM-AHU-ERV")
    assert alias is not None
    assert alias["stub_patch_name"] == "erv_ahu_prototype"

    assert is_prototype_residual_patch("erv_ahu_prototype")
    assert "erv_ahu_prototype" not in known_patch_names()
    assert any(r["ticket"] == "ECM-ERV-001" for r in list_prototype_residuals())

    entry = get_ecm("ECM-ERV")
    assert entry.energyplus_patch is None
    assert entry.status == "PRODUCTION_PROXY_ONLY"

    src = tmp_path / "a.idf"
    dest = tmp_path / "b.idf"
    src.write_text("Version,26.1;\n", encoding="utf-8")
    with pytest.raises(ValueError, match="HAS_EP_PROTOTYPE"):
        apply_patch("erv_ahu_prototype", src, dest)
