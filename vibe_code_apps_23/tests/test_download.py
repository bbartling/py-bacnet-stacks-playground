import stat
import zipfile
from pathlib import Path

import pytest

from vibe23.download import download_dataset, safe_extract, sha256_file


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


def test_safe_extract_rejects_symlink(tmp_path: Path):
    archive = tmp_path / "bad-link.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        info = zipfile.ZipInfo("link")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        zf.writestr(info, "target")
    with pytest.raises(ValueError, match="symlink"):
        safe_extract(archive, tmp_path / "out")


def test_safe_extract_rejects_case_collision(tmp_path: Path):
    archive = tmp_path / "bad-collision.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("Data/A.csv", "a")
        zf.writestr("data/a.csv", "b")
    with pytest.raises(ValueError, match="case-colliding"):
        safe_extract(archive, tmp_path / "out")


def test_manual_release_directory_is_staged_and_hashed(tmp_path: Path):
    release = tmp_path / "release"
    release.mkdir()
    with zipfile.ZipFile(release / "Building_59.zip", "w") as zf:
        zf.writestr("energy.csv", "timestamp,power_kw\n2019-01-01,1\n")
    for name in (
        "data_description_table_3year_clean_data.xlsx",
        "metadata_Dryad_Bldg59.docx",
        "README_Dryad_Bldg59.txt",
    ):
        (release / name).write_bytes(b"fixture")

    manifest = download_dataset(tmp_path / "data", source_release=release)

    assert manifest["acquisition_mode"] == "manual_release_directory"
    assert manifest["package"] is None
    assert len(manifest["building_zip"]["sha256"]) == 64
    assert (tmp_path / "data/raw/building_59/energy.csv").is_file()


def test_manual_source_cannot_point_at_generated_release(tmp_path: Path):
    generated = tmp_path / "data/raw/dryad_release"
    generated.mkdir(parents=True)
    with pytest.raises(ValueError, match="outside"):
        download_dataset(tmp_path / "data", source_release=generated)
