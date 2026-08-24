import stat
import urllib.request
import zipfile
from pathlib import Path

import pytest

from vibe23 import download
from vibe23.download import _AuthorizationSafeRedirectHandler, download_dataset, md5_file, safe_extract, sha256_file


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
    assert md5_file(path) == "900150983cd24fb0d6963f7d28e17f72"


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


def test_cross_origin_redirect_strips_authorization():
    handler = _AuthorizationSafeRedirectHandler()
    request = urllib.request.Request(
        "https://datadryad.org/source", headers={"Authorization": "Bearer secret"}
    )
    redirected = handler.redirect_request(
        request, None, 302, "Found", {}, "https://storage.example.net/archive.zip"
    )
    assert redirected is not None
    assert redirected.get_header("Authorization") is None


def test_manual_restage_rebuilds_telemetry_from_new_release(tmp_path: Path):
    def make_release(root: Path, value: str) -> Path:
        root.mkdir()
        with zipfile.ZipFile(root / "Building_59.zip", "w") as zf:
            zf.writestr("energy.csv", f"timestamp,power_kw\n2019-01-01,{value}\n")
        for name in (
            "data_description_table_3year_clean_data.xlsx",
            "metadata_Dryad_Bldg59.docx",
            "README_Dryad_Bldg59.txt",
        ):
            (root / name).write_bytes(value.encode())
        return root

    first = make_release(tmp_path / "release-a", "1")
    second = make_release(tmp_path / "release-b", "2")
    data = tmp_path / "data"
    download_dataset(data, source_release=first)
    download_dataset(data, source_release=second)
    assert (data / "raw/building_59/energy.csv").read_text(encoding="utf-8").endswith(",2\n")


def test_zenodo_mirror_fallback_validates_published_md5_and_records_provenance(tmp_path: Path, monkeypatch):
    payloads = {
        "Building_59.zip": None,
        "data_description_table_3year_clean_data.xlsx": b"workbook",
        "metadata_Dryad_Bldg59.docx": b"metadata",
        "README_Dryad_Bldg59.txt": b"readme",
    }
    building_zip = tmp_path / "fixture-building.zip"
    with zipfile.ZipFile(building_zip, "w") as archive:
        archive.writestr("energy.csv", "timestamp,power_kw\n2019-01-01,1\n")
    payloads["Building_59.zip"] = building_zip.read_bytes()
    checksums = {name: __import__("hashlib").md5(body).hexdigest() for name, body in payloads.items()}
    monkeypatch.setattr(download, "ZENODO_PUBLISHED_MD5", checksums)

    def fake_download(url: str, destination: Path, *, bearer_token=None):
        if "datadryad.org" in url:
            raise RuntimeError("rejected")
        name = destination.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payloads[name])

    monkeypatch.setattr(download, "_download", fake_download)
    manifest = download_dataset(tmp_path / "data")

    assert manifest["acquisition_mode"] == "zenodo_mirror_fallback"
    assert manifest["canonical_source"]["doi"] == "10.7941/D1N33Q"
    assert manifest["mirror_source"]["record_id"] == "5951008"
    assert manifest["mirror_source"]["md5_validation"] == "passed"
    assert manifest["mirror_source"]["published_md5"] == checksums
