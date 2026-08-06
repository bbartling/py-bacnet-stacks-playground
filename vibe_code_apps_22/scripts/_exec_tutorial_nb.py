"""Execute tutorial notebooks with a clean kernel."""
from __future__ import annotations

import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
NB_DIR = ROOT / "notebooks"


def run(path: Path, timeout: int = 3600) -> None:
    nb = nbformat.read(path, as_version=4)
    client = NotebookClient(
        nb,
        timeout=timeout,
        kernel_name="python3",
        resources={"metadata": {"path": str(path.parent)}},
    )
    print(f"EXEC {path}", flush=True)
    client.execute()
    nbformat.write(nb, path)
    for i, c in enumerate(nb.cells):
        for o in c.get("outputs", []):
            if o.get("output_type") == "error":
                raise SystemExit(f"cell {i} error: {o.get('ename')} {o.get('evalue')}")
    print(f"OK {path} cells={len(nb.cells)}", flush=True)


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else "torch"
    if which == "torch":
        run(NB_DIR / "lakeside_heating_dsm_torch.ipynb", timeout=1800)
    elif which == "sklearn":
        run(NB_DIR / "lakeside_heating_dsm_sklearn.ipynb", timeout=7200)
    else:
        raise SystemExit("usage: _exec_tutorial_nb.py [torch|sklearn]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
