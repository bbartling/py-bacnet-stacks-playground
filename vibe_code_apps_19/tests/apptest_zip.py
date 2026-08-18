"""Shared AppTest helper: load a package zip the same way a human does."""

from __future__ import annotations

from pathlib import Path


def load_zip_via_uploader(at, zpath: Path):
    data = zpath.read_bytes() if isinstance(zpath, Path) else zpath
    name = zpath.name if isinstance(zpath, Path) else "pkg.zip"
    uploader = None
    for fu in at.sidebar.file_uploader:
        if (fu.label or "") == "Building package zip(s)":
            uploader = fu
            break
    assert uploader is not None, "Building package zip(s) uploader missing"
    uploader.set_value((name, data if isinstance(data, bytes) else Path(zpath).read_bytes(), "application/zip"))
    at.run()
    load_btn = next((b for b in at.sidebar.button if (b.label or "") == "Load zip(s)"), None)
    assert load_btn is not None, "Load zip(s) button missing"
    load_btn.click().run()
    return at
