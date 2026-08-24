from pathlib import Path
import zipfile

import pytest

from vibe23.download import safe_extract, sha256_file


def test_safe_extract_rejects_path_traversal(tmp_path: Path):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../escape.txt", "nope")
    with pytest.raises(ValueError, match="Unsafe ZIP"):
        safe_extract(archive, tmp_path / "out")


def test_sha256_file_is_stable(tmp_path: Path):
    path = tmp_path / "x.txt"
    path.write_text("abc", encoding="utf-8")
    assert sha256_file(path) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
