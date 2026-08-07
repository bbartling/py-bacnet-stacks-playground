"""Execute Lakeside notebooks in order (smoke promote env assumed set by caller)."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
NB_DIR = ROOT / "notebooks"

NOTEBOOKS = [
    "lakeside_load_profile_analysis.ipynb",
    "lakeside_heating_dsm_sklearn.ipynb",
    "lakeside_heating_dsm_torch.ipynb",
]


def run_one(name: str, timeout: int = 7200) -> None:
    path = NB_DIR / name
    print(f"\n=== EXECUTE {name} ===", flush=True)
    t0 = time.time()
    nb = nbformat.read(path, as_version=4)
    client = NotebookClient(
        nb,
        timeout=timeout,
        kernel_name="python3",
        resources={"metadata": {"path": str(NB_DIR)}},
    )
    client.execute()
    nbformat.write(nb, path)
    print(f"=== DONE {name} in {time.time() - t0:.1f}s ===", flush=True)


def main() -> int:
    os.environ.setdefault(
        "LAKESIDE_SITE_ROOT",
        r"C:\Users\ben\OneDrive\Desktop\testing\sp_creekside",
    )
    os.environ["VIBE22_ALLOW_SMOKE_PROMOTE"] = "1"
    only = sys.argv[1:] if len(sys.argv) > 1 else NOTEBOOKS
    for name in only:
        run_one(name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
