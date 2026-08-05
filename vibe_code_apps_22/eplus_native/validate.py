"""Fail-closed acceptance gates for native EnergyPlus runs."""
from __future__ import annotations

from pathlib import Path

from eplus_native.err_parse import parse_eplusout_err
from eplus_native.manifest import RunManifest, mark_accepted


REQUIRED_OUTPUTS = (
    "eplusout.err",
    "eplusout.csv",
)


def validate_run(
    manifest: RunManifest,
    *,
    require_zero_severe: bool = True,
    require_outputs: tuple[str, ...] = REQUIRED_OUTPUTS,
) -> RunManifest:
    reasons: list[str] = []
    out = Path(manifest.output_dir)
    if not out.is_dir():
        reasons.append(f"missing output_dir {out}")
    for name in require_outputs:
        if not (out / name).is_file():
            reasons.append(f"missing native output {name}")
    err_path = out / "eplusout.err"
    if err_path.is_file():
        err = parse_eplusout_err(err_path)
        manifest.warning_count = err.warnings
        manifest.severe_count = err.severes
        manifest.fatal_count = err.fatals
        if err.fatals > 0:
            reasons.append(f"fatal errors: {err.fatals}")
        if require_zero_severe and err.severes > 0:
            reasons.append(f"severe errors: {err.severes} (zero required)")
        if not err.completed_successfully and manifest.exit_code == 0:
            reasons.append("eplusout.err did not report Completed Successfully")
    else:
        reasons.append("cannot parse eplusout.err")
    if manifest.exit_code != 0:
        reasons.append(f"nonzero exit_code={manifest.exit_code}")
    if not manifest.idf_sha256 or not manifest.epw_sha256:
        reasons.append("missing idf/epw sha256")
    if not manifest.proxy_formula_version:
        reasons.append("missing proxy_formula_version")

    manifest.reject_reasons = reasons
    if reasons:
        manifest.accepted = False
        manifest.provenance = ""
        return manifest
    return mark_accepted(manifest)
