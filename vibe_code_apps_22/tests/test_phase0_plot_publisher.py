from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from plots.phase0_plot_publisher import publish_phase0_allowlisted_plots


PNG_1X1_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO5yR0kAAAAASUVORK5CYII="
)

SVG_NATIVE_BYTES = b"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">
  <rect width="10" height="10" fill="red"/>
</svg>
"""

SVG_EMBEDDED_PNG_BYTES = b"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">
  <image href="data:image/png;base64,AAAA" width="10" height="10"/>
</svg>
"""


def _write_manifest(path: Path, *, claim_label: str) -> Path:
    manifest = {
        "schema": "vibe22.phase0.plot_manifest.v1",
        "claim_label": claim_label,
        "generator": {"generator_script_sha256": "A" * 64},
        "allowlist": [
            {
                "plot_id": "required_plot",
                "availability": "required_existing",
                "source": {"png": "src/required.png", "svg": "src/required.svg"},
                "dest": {"png": "plots/calibration/required.png", "svg": "plots/calibration/required.svg"},
            },
            {
                "plot_id": "future_optional_plot",
                "availability": "future_optional",
                "source": {"png": "src/optional.png", "svg": "src/optional.svg"},
                "dest": {"png": "plots/calibration/optional.png", "svg": "plots/calibration/optional.svg"},
            },
        ],
    }
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path


def test_required_existing_missing_raises(tmp_path: Path) -> None:
    source_root = tmp_path / "site_root"
    dest_root = tmp_path / "repo_plots"
    source_root.mkdir()
    dest_root.mkdir()

    # Create PNG but not SVG for required plot.
    (source_root / "src").mkdir(parents=True, exist_ok=True)
    (source_root / "src" / "required.png").write_bytes(PNG_1X1_BYTES)

    manifest_path = _write_manifest(tmp_path / "plot_manifest.json", claim_label="c")
    out_manifest = dest_root / "source_manifest.json"

    with pytest.raises(FileNotFoundError):
        publish_phase0_allowlisted_plots(
            manifest_path=manifest_path,
            source_root=source_root,
            dest_root=dest_root,
            out_source_manifest_path=out_manifest,
        )


def test_future_optional_missing_is_not_run(tmp_path: Path) -> None:
    source_root = tmp_path / "site_root"
    dest_root = tmp_path / "repo_plots"
    source_root.mkdir()
    dest_root.mkdir()

    # Create required plot sources.
    (source_root / "src").mkdir(parents=True, exist_ok=True)
    (source_root / "src" / "required.png").write_bytes(PNG_1X1_BYTES)
    (source_root / "src" / "required.svg").write_bytes(SVG_NATIVE_BYTES)

    # Do NOT create optional plot sources (future optional => NOT_RUN).
    manifest_path = _write_manifest(tmp_path / "plot_manifest.json", claim_label="c")
    out_manifest = dest_root / "source_manifest.json"

    publish_phase0_allowlisted_plots(
        manifest_path=manifest_path,
        source_root=source_root,
        dest_root=dest_root,
        out_source_manifest_path=out_manifest,
    )

    # Required files copied.
    assert (dest_root / "plots" / "calibration" / "required.png").is_file()
    assert (dest_root / "plots" / "calibration" / "required.svg").is_file()

    # Optional NOT_RUN => no dest files created.
    assert not (dest_root / "plots" / "calibration" / "optional.png").exists()
    assert not (dest_root / "plots" / "calibration" / "optional.svg").exists()

    prov = json.loads(out_manifest.read_text(encoding="utf-8"))
    recs = {r["plot_id"]: r for r in prov["plot_records"]}
    assert recs["future_optional_plot"]["status"] == "NOT_RUN"


def test_future_optional_stale_dest_raises(tmp_path: Path) -> None:
    source_root = tmp_path / "site_root"
    dest_root = tmp_path / "repo_plots"
    source_root.mkdir()
    dest_root.mkdir()

    # Create required plot sources only.
    (source_root / "src").mkdir(parents=True, exist_ok=True)
    (source_root / "src" / "required.png").write_bytes(PNG_1X1_BYTES)
    (source_root / "src" / "required.svg").write_bytes(SVG_NATIVE_BYTES)

    # Create stale destination optional files even though sources are missing.
    (dest_root / "plots" / "calibration").mkdir(parents=True, exist_ok=True)
    (dest_root / "plots" / "calibration" / "optional.png").write_bytes(PNG_1X1_BYTES)
    (dest_root / "plots" / "calibration" / "optional.svg").write_bytes(SVG_NATIVE_BYTES)

    manifest_path = _write_manifest(tmp_path / "plot_manifest.json", claim_label="c")
    out_manifest = dest_root / "source_manifest.json"

    with pytest.raises(ValueError, match="stale plot present"):
        publish_phase0_allowlisted_plots(
            manifest_path=manifest_path,
            source_root=source_root,
            dest_root=dest_root,
            out_source_manifest_path=out_manifest,
        )


def test_svg_embedded_png_raises(tmp_path: Path) -> None:
    source_root = tmp_path / "site_root"
    dest_root = tmp_path / "repo_plots"
    source_root.mkdir()
    dest_root.mkdir()

    (source_root / "src").mkdir(parents=True, exist_ok=True)
    (source_root / "src" / "required.png").write_bytes(PNG_1X1_BYTES)
    (source_root / "src" / "required.svg").write_bytes(SVG_EMBEDDED_PNG_BYTES)

    manifest_path = _write_manifest(tmp_path / "plot_manifest.json", claim_label="c")
    out_manifest = dest_root / "source_manifest.json"

    with pytest.raises(ValueError, match="SVG appears to embed"):
        publish_phase0_allowlisted_plots(
            manifest_path=manifest_path,
            source_root=source_root,
            dest_root=dest_root,
            out_source_manifest_path=out_manifest,
        )


def test_reproducible_rerun_stable_manifest_hash(tmp_path: Path) -> None:
    source_root = tmp_path / "site_root"
    dest_root = tmp_path / "repo_plots"
    source_root.mkdir()
    dest_root.mkdir()

    (source_root / "src").mkdir(parents=True, exist_ok=True)
    (source_root / "src" / "required.png").write_bytes(PNG_1X1_BYTES)
    (source_root / "src" / "required.svg").write_bytes(SVG_NATIVE_BYTES)

    manifest_path = _write_manifest(tmp_path / "plot_manifest.json", claim_label="c")
    out_manifest = dest_root / "source_manifest.json"

    publish_phase0_allowlisted_plots(
        manifest_path=manifest_path,
        source_root=source_root,
        dest_root=dest_root,
        out_source_manifest_path=out_manifest,
    )
    first = json.loads(out_manifest.read_text(encoding="utf-8"))

    publish_phase0_allowlisted_plots(
        manifest_path=manifest_path,
        source_root=source_root,
        dest_root=dest_root,
        out_source_manifest_path=out_manifest,
    )
    second = json.loads(out_manifest.read_text(encoding="utf-8"))

    assert first["provenance_manifest_sha256"] == second["provenance_manifest_sha256"]
    assert first["plot_records"] == second["plot_records"]

