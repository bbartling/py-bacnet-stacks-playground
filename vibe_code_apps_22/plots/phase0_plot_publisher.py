"""Phase 0 manifest-driven allowlist publisher.

Goal: copy a curated set of already-rendered plot artifacts (PNG + native SVG)
from a render-only SITE_ROOT into the curated repo `vibe_code_apps_22/plots/...`
subdirectories, with fail-closed behavior and reproducible provenance manifests.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from eplus_native.hashes import sha256_file

Format = Literal["png", "svg"]
Availability = Literal["required_existing", "future_optional"]


def _stable_json_dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_text(text: str) -> str:
    h = hashlib.sha256()
    h.update(text.encode("utf-8"))
    return h.hexdigest().upper()


def _rel_posix(p: Path) -> str:
    return p.as_posix()


def _validate_native_svg(svg_bytes: bytes) -> None:
    # Fail closed if SVG appears to embed a raster image payload.
    # This enforces: "native SVG and PNG from the same plotting source" and
    # "do not wrap raster PNGs inside SVG files".
    s = svg_bytes.decode("utf-8", errors="ignore")
    suspicious = (
        "data:image/png",
        "image/png",
        "xlink:href=\"data:image/png",
        "href=\"data:image/png",
        "data:image/jpeg",
        "data:image/webp",
    )
    if any(tok in s for tok in suspicious):
        raise ValueError("SVG appears to embed a raster image payload (fail closed).")

    # Very light sanity: should look like SVG markup.
    if not re.search(r"<svg\b", s, flags=re.IGNORECASE):
        raise ValueError("SVG does not appear to contain an <svg ...> root tag.")


@dataclass(frozen=True)
class PlotSpec:
    plot_id: str
    availability: Availability
    source_rel_png: Path
    source_rel_svg: Path
    dest_rel_png: Path
    dest_rel_svg: Path


def load_phase0_plot_manifest(path: Path | str) -> dict[str, Any]:
    p = Path(path)
    raw = json.loads(p.read_text(encoding="utf-8"))
    if raw.get("schema") != "vibe22.phase0.plot_manifest.v1":
        raise ValueError(f"unexpected manifest schema: {raw.get('schema')!r}")
    return raw


def parse_plot_specs(manifest: dict[str, Any]) -> list[PlotSpec]:
    specs: list[PlotSpec] = []
    for row in manifest.get("allowlist") or []:
        plot_id = row.get("plot_id")
        availability = row.get("availability")
        src = row.get("source") or {}
        dst = row.get("dest") or {}
        if not plot_id or availability not in {"required_existing", "future_optional"}:
            raise ValueError(f"invalid allowlist entry: {row!r}")

        # Require both png + svg to be defined for every allowlisted plot.
        for k in ("png", "svg"):
            if k not in src or k not in dst:
                raise ValueError(f"allowlist entry missing png/svg keys: {row!r}")

        specs.append(
            PlotSpec(
                plot_id=str(plot_id),
                availability=str(availability),  # type: ignore[arg-type]
                source_rel_png=Path(str(src["png"])),
                source_rel_svg=Path(str(src["svg"])),
                dest_rel_png=Path(str(dst["png"])),
                dest_rel_svg=Path(str(dst["svg"])),
            )
        )
    return specs


def _source_exists(source_root: Path, rel_path: Path) -> bool:
    return (source_root / rel_path).is_file()


def _copy_if_needed(*, src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        # Fail closed on any hash mismatch to avoid silently keeping stale content.
        if sha256_file(dst) != sha256_file(src):
            raise ValueError(f"stale dest content hash mismatch for {dst}")
        return
    dst.write_bytes(src.read_bytes())


def publish_phase0_allowlisted_plots(
    *,
    manifest_path: Path | str,
    source_root: Path | str,
    dest_root: Path | str,
    out_source_manifest_path: Path | str,
    command_label: str = "vibe22.phase0_plot_publisher",
) -> Path:
    """Copy allowlisted plot outputs and write a deterministic provenance manifest.

    Fail-closed semantics:
    - required_existing: missing either PNG or SVG sources => raise
    - future_optional: missing either PNG or SVG sources => do not copy and record NOT_RUN
    - native SVG constraint: if SVG embeds raster payload => raise
    - stale outputs: if destination already contains a file for an entry that should be NOT_RUN,
      or if destination hashes mismatch the source, => raise.
    """

    manifest_path = Path(manifest_path)
    source_root = Path(source_root)
    dest_root = Path(dest_root)
    out_source_manifest_path = Path(out_source_manifest_path)

    manifest = load_phase0_plot_manifest(manifest_path)
    claim_label = manifest.get("claim_label") or "unknown_claim"
    generator = manifest.get("generator") or {}
    generator_script_sha = generator.get("generator_script_sha256")
    if not generator_script_sha:
        raise ValueError("manifest.generator.generator_script_sha256 required")

    specs = parse_plot_specs(manifest)

    plot_records: list[dict[str, Any]] = []

    for spec in specs:
        src_png = source_root / spec.source_rel_png
        src_svg = source_root / spec.source_rel_svg
        dst_png = dest_root / spec.dest_rel_png
        dst_svg = dest_root / spec.dest_rel_svg

        have_png = src_png.is_file()
        have_svg = src_svg.is_file()

        if have_png and have_svg:
            svg_bytes = src_svg.read_bytes()
            _validate_native_svg(svg_bytes)

            _copy_if_needed(src=src_png, dst=dst_png)
            _copy_if_needed(src=src_svg, dst=dst_svg)

            plot_records.append(
                {
                    "plot_id": spec.plot_id,
                    "availability": spec.availability,
                    "status": "COPIED",
                    "png": {
                        "source_rel": _rel_posix(spec.source_rel_png),
                        "dest_rel": _rel_posix(spec.dest_rel_png),
                        "source_sha256": sha256_file(src_png),
                        "source_bytes": src_png.stat().st_size,
                    },
                    "svg": {
                        "source_rel": _rel_posix(spec.source_rel_svg),
                        "dest_rel": _rel_posix(spec.dest_rel_svg),
                        "source_sha256": sha256_file(src_svg),
                        "source_bytes": src_svg.stat().st_size,
                    },
                }
            )
            continue

        # One or both sources missing.
        should_run = spec.availability == "required_existing"

        # If dest already has something, that is stale (fail closed).
        if dst_png.exists() or dst_svg.exists():
            raise ValueError(
                f"stale plot present for NOT_RUN entry {spec.plot_id} (dest files already exist)"
            )

        if should_run:
            missing = []
            if not have_png:
                missing.append(f"missing png source: {spec.source_rel_png}")
            if not have_svg:
                missing.append(f"missing svg source: {spec.source_rel_svg}")
            raise FileNotFoundError(f"required plot missing sources for {spec.plot_id}: {missing}")

        # Future optional: explicit NOT_RUN.
        plot_records.append(
            {
                "plot_id": spec.plot_id,
                "availability": spec.availability,
                "status": "NOT_RUN",
                "png": {
                    "source_rel": _rel_posix(spec.source_rel_png),
                    "dest_rel": _rel_posix(spec.dest_rel_png),
                    "missing": not have_png,
                },
                "svg": {
                    "source_rel": _rel_posix(spec.source_rel_svg),
                    "dest_rel": _rel_posix(spec.dest_rel_svg),
                    "missing": not have_svg,
                },
            }
        )

    out_body: dict[str, Any] = {
        "schema": "vibe22.phase0.source_manifest.v1",
        "claim_label": claim_label,
        "generator_script_sha256": generator_script_sha,
        "command_label": command_label,
        "plot_records": plot_records,
    }

    # Stable manifest hash should NOT depend on runtime timestamps.
    blob = _stable_json_dumps(out_body).encode("utf-8")
    out_body["provenance_manifest_sha256"] = hashlib.sha256(blob).hexdigest().upper()

    out_source_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    out_source_manifest_path.write_text(_stable_json_dumps(out_body) + "\n", encoding="utf-8")
    return out_source_manifest_path

