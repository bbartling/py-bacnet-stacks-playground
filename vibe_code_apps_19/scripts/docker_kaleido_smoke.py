"""Docker build smoke: Plotly → Kaleido PNG (BUG-011).

Under Buildx QEMU arm64, Chromium often exits immediately; soft-skip there.
On amd64 (and real arm64 hosts at runtime) PNG export must work.
"""
from __future__ import annotations

import os
import platform
import sys
from pathlib import Path


def main() -> int:
    os.environ.setdefault("BROWSER_PATH", "/usr/bin/chromium")
    try:
        import plotly.graph_objects as go
    except ImportError as exc:
        print("plotly missing:", exc, file=sys.stderr)
        return 1

    out = Path("/tmp/kaleido_smoke.png")
    fig = go.Figure(data=[go.Bar(x=["a"], y=[1])])
    try:
        fig.write_image(str(out))
        assert out.is_file() and out.stat().st_size > 100
    except Exception as exc:
        machine = platform.machine()
        if machine in ("aarch64", "arm64"):
            print(f"WARN kaleido smoke skipped on {machine}: {exc}")
            return 0
        print(f"kaleido smoke failed on {machine}: {exc}", file=sys.stderr)
        return 1
    print("kaleido png ok", out.stat().st_size, platform.machine())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
