"""Fail-closed ramp_gate.json destination. Candidates must not overwrite A04."""
from __future__ import annotations

from pathlib import Path

from eplus_gym.a04_identity import is_canonical_a04_idf_filename

CANONICAL_RAMP_REL = Path("docs") / "audits" / "figures" / "postfix" / "ramp_gate.json"


class RampArtifactError(ValueError):
    """Candidate run attempted to replace the frozen A04 ramp artifact."""


def canonical_ramp_gate_path(app_root: Path) -> Path:
    return Path(app_root) / CANONICAL_RAMP_REL


def resolve_ramp_artifact_dest(
    *,
    app_root: Path,
    out: Path,
    write_artifact: Path | None,
    idf: Path | None,
) -> Path:
    """Return where to write ramp_gate.json.

    A candidate IDF may never land on the committed A04 postfix artifact,
    even when ``--write-artifact`` is passed.
    """
    app_root = Path(app_root)
    canonical = canonical_ramp_gate_path(app_root).resolve()
    dest = Path(write_artifact) if write_artifact is not None else canonical
    if idf is not None and not is_canonical_a04_idf_filename(Path(idf).name):
        if dest.resolve() == canonical:
            if write_artifact is None:
                return Path(out) / "ramp_gate.json"
            raise RampArtifactError(
                "candidate IDF cannot overwrite canonical postfix/ramp_gate.json"
            )
    return dest
