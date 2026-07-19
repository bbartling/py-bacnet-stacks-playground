"""Read-only XLSX package metadata inspection for private audit workflows."""

from __future__ import annotations

from pathlib import Path
from zipfile import BadZipFile, ZipFile
import xml.etree.ElementTree as ET


def inspect_xlsx(path: str | Path) -> dict[str, object]:
    """Inspect an XLSX zip for external-link parts and Dublin Core properties."""

    source = Path(path)
    try:
        with ZipFile(source) as archive:
            names = archive.namelist()
            external_links = sorted(
                name
                for name in names
                if name.casefold().startswith("xl/externallinks/")
            )
            core_properties = _read_core_properties(archive)
    except BadZipFile as exc:
        raise ValueError(f"not a valid XLSX zip package: {source}") from exc

    return {
        "path": str(source),
        "external_links": external_links,
        "has_external_links": bool(external_links),
        "core_properties": core_properties,
    }


def _read_core_properties(archive: ZipFile) -> dict[str, str]:
    try:
        xml = archive.read("docProps/core.xml")
    except KeyError:
        return {}

    root = ET.fromstring(xml)
    properties: dict[str, str] = {}
    for child in root:
        value = (child.text or "").strip()
        if value:
            properties[child.tag.rsplit("}", 1)[-1]] = value
    return properties
