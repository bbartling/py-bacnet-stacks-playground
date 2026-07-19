"""Repository-level privacy guardrails for WattLab."""

from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from wattlab.privacy.deny_list import scan_text, scan_tree, sha256_norm
from wattlab.privacy.scan import find_forbidden_binaries
from wattlab.privacy.workbook_metadata import inspect_xlsx


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_constructed_prohibited_name_is_detected() -> None:
    first_word = "".join(["char", "les"])
    prohibited = " ".join([first_word, "county", "public", "schools"])

    hits = scan_text(f"unrelated prefix {prohibited} unrelated suffix")

    assert [hit["sha256"] for hit in hits] == [sha256_norm(prohibited)]


def test_repository_text_has_no_deny_list_matches() -> None:
    hits = scan_tree(PROJECT_ROOT)

    assert hits == [], "\n".join(
        f"{hit['path']}:{hit.get('line', '?')} [{hit['sha256']}]" for hit in hits
    )


def test_repository_contains_no_spreadsheet_workbooks() -> None:
    binaries = find_forbidden_binaries(PROJECT_ROOT)

    assert binaries == [], "\n".join(str(path) for path in binaries)


def test_xlsx_audit_reports_external_links_and_core_properties(tmp_path: Path) -> None:
    workbook = tmp_path / "audit-input.xlsx"
    with ZipFile(workbook, "w") as archive:
        archive.writestr("xl/externalLinks/externalLink1.xml", "<externalLink/>")
        archive.writestr(
            "docProps/core.xml",
            (
                '<cp:coreProperties xmlns:cp="urn:core" xmlns:dc="urn:dc">'
                "<dc:creator>Audit Author</dc:creator>"
                "</cp:coreProperties>"
            ),
        )

    metadata = inspect_xlsx(workbook)

    assert metadata["has_external_links"] is True
    assert metadata["external_links"] == ["xl/externalLinks/externalLink1.xml"]
    assert metadata["core_properties"] == {"creator": "Audit Author"}
