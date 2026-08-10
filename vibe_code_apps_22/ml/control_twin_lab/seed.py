"""A04 seed resolution and staged IDF copies — champion is read-only."""
from __future__ import annotations

import hashlib
from pathlib import Path

from physics_families import A04_CHAMPION_IDF, W2A_PHYSICAL_DSM, resolve_w2a_dsm_seed

PROVENANCE = "SYNTHETIC_W2A_PROVENANCE"
HONESTY_LAB = "CONTROL_TWIN_LAB_V1"
PROMOTE = "NON_PROMOTABLE"

# Reuse scaffold patching
import sys

_APP = Path(__file__).resolve().parents[2]
if str(_APP / "scripts") not in sys.path:
    sys.path.insert(0, str(_APP / "scripts"))

from eplus_w2a_dsm_farm_scaffold import EXTRA_OUTPUTS, patch_timestep  # noqa: E402


def champion_sha256() -> str:
    seed = resolve_w2a_dsm_seed()
    return hashlib.sha256(seed.read_bytes()).hexdigest()


def assert_champion_untouched(before_sha: str) -> None:
    after = champion_sha256()
    if after != before_sha:
        raise RuntimeError(
            f"A04 champion was modified during lab run "
            f"(before={before_sha[:12]} after={after[:12]}) — abort"
        )


def stage_lab_idf(
    *,
    out_dir: Path,
    steps_per_hour: int = 6,
    tag: str = "lab",
) -> Path:
    """Copy A04 → staged lab IDF under out_dir; never write champion path."""
    seed = resolve_w2a_dsm_seed()
    if seed.resolve() == Path(out_dir).resolve() / seed.name:
        raise ValueError("refusing to stage into champion directory")
    text = seed.read_text(encoding="utf-8", errors="replace")
    text = patch_timestep(text, steps_per_hour)
    if "W2A_PHYSICAL_DSM scaffold outputs" not in text:
        text = text.rstrip() + "\n" + EXTRA_OUTPUTS
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"w2a_ctl_lab_{tag}_ts{steps_per_hour}.idf"
    if out.resolve() == seed.resolve():
        raise ValueError("staged path collides with champion")
    out.write_text(text, encoding="utf-8")
    meta = out_dir / f"{out.stem}_meta.txt"
    meta.write_text(
        f"physics_family={W2A_PHYSICAL_DSM}\n"
        f"honesty={HONESTY_LAB}\n"
        f"provenance={PROVENANCE}\n"
        f"promote={PROMOTE}\n"
        f"seed={seed}\n"
        f"seed_sha256={champion_sha256()}\n"
        f"staged={out}\n"
        f"note=SYNTHETIC lab seed copy — not field plant truth\n",
        encoding="utf-8",
    )
    return out
