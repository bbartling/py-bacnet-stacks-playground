"""Generate minimal placeholder .docx files under assets/reports (no python-docx).

Re-run after adding a new mechanical report slot. Engineers paste real Word files
over these dummies; the app serves whatever is on disk.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "reports"

# (filename, title, body paragraphs)
REPORTS: list[tuple[str, str, list[str]]] = [
    (
        "fdd_ahu.docx",
        "FDD report — AHU (dummy)",
        [
            "KEY FINDINGS — replace this file with your AHU FDD Word report.",
            "Description: Placeholder AHU fault cards.",
            "Equation: (engineer paste)",
            "[PLACE PLOT HERE]",
        ],
    ),
    (
        "fdd_vav.docx",
        "FDD report — VAV (dummy)",
        [
            "KEY FINDINGS — replace this file with your VAV FDD Word report.",
            "Description: Placeholder VAV fault cards.",
            "Equation: (engineer paste)",
            "[PLACE PLOT HERE]",
        ],
    ),
    (
        "fdd_boiler.docx",
        "FDD report — Boiler (dummy)",
        [
            "KEY FINDINGS — replace this file with your boiler FDD Word report.",
            "Description: Placeholder boiler fault cards.",
            "Equation: (engineer paste)",
            "[PLACE PLOT HERE]",
        ],
    ),
    (
        "fdd_chiller.docx",
        "FDD report — Chiller / CHW plant (dummy)",
        [
            "KEY FINDINGS — replace this file with your chiller FDD Word report.",
            "Description: Placeholder chiller fault cards.",
            "Equation: (engineer paste)",
            "[PLACE PLOT HERE]",
        ],
    ),
    (
        "fdd_cooling_tower.docx",
        "FDD report — Cooling tower (dummy)",
        [
            "KEY FINDINGS — replace this file with your cooling-tower FDD Word report.",
            "Description: Placeholder tower fault cards.",
            "Equation: (engineer paste)",
            "[PLACE PLOT HERE]",
        ],
    ),
    (
        "fdd_hp.docx",
        "FDD report — Heat pump (dummy)",
        [
            "KEY FINDINGS — replace this file with your heat-pump FDD Word report.",
            "Description: Placeholder HP fault cards.",
            "Equation: (engineer paste)",
            "[PLACE PLOT HERE]",
        ],
    ),
    (
        "fdd_meter.docx",
        "FDD report — Meter (dummy)",
        [
            "KEY FINDINGS — replace this file with your meter FDD Word report.",
            "Description: Placeholder meter cards.",
            "Equation: (engineer paste)",
            "[PLACE PLOT HERE]",
        ],
    ),
    (
        "fdd_weather.docx",
        "FDD report — Weather (dummy)",
        [
            "KEY FINDINGS — replace this file with your weather FDD Word report.",
            "Description: Placeholder weather cards.",
            "Equation: (engineer paste)",
            "[PLACE PLOT HERE]",
        ],
    ),
    (
        "fdd_generic.docx",
        "FDD report — Generic (dummy)",
        [
            "KEY FINDINGS — replace this file with a type-specific FDD Word report.",
            "Description: Fallback when equipment type is unknown.",
            "Equation: (engineer paste)",
            "[PLACE PLOT HERE]",
        ],
    ),
    (
        "rcx_zones_vav.docx",
        "RCx report — Zones / VAV (dummy)",
        [
            "KEY FINDINGS — replace with Zones/VAV RCx Word report.",
            "[PLACE RCX PLOT HERE]",
        ],
    ),
    (
        "rcx_ahu_air.docx",
        "RCx report — AHU / air (dummy)",
        [
            "KEY FINDINGS — replace with AHU/air RCx Word report.",
            "[PLACE RCX PLOT HERE]",
        ],
    ),
    (
        "rcx_boiler_hw.docx",
        "RCx report — Boiler / HW (dummy)",
        [
            "KEY FINDINGS — replace with Boiler/HW RCx Word report.",
            "[PLACE RCX PLOT HERE]",
        ],
    ),
    (
        "rcx_chiller_chw_tower.docx",
        "RCx report — Chiller / CHW / tower (dummy)",
        [
            "KEY FINDINGS — replace with Chiller/CHW/tower RCx Word report.",
            "[PLACE RCX PLOT HERE]",
        ],
    ),
    (
        "rcx_metering.docx",
        "RCx report — Metering (dummy)",
        [
            "KEY FINDINGS — replace with Metering RCx Word report.",
            "[PLACE RCX PLOT HERE]",
        ],
    ),
    (
        "rcx_catalog.docx",
        "RCx catalog (dummy)",
        [
            "KEY FINDINGS — full RCx catalog stub for Export; prefer family files on RCx Plots.",
            "[PLACE RCX PLOT HERE]",
        ],
    ),
    (
        "data_model.docx",
        "Data model report (dummy)",
        [
            "KEY FINDINGS — replace with building data-model Word report.",
            "Equipment → cookbook roles → CSV columns (paste tables here).",
        ],
    ),
    (
        "analytics.docx",
        "Analytics report (dummy)",
        [
            "KEY FINDINGS — replace with analytics Word report.",
            "Motor weekly / cool bins / RCx coverage (paste tables here).",
        ],
    ),
]


def _document_xml(title: str, paragraphs: list[str]) -> bytes:
    parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">',
        "<w:body>",
        f"<w:p><w:r><w:t>{escape(title)}</w:t></w:r></w:p>",
    ]
    for para in paragraphs:
        parts.append(f"<w:p><w:r><w:t>{escape(para)}</w:t></w:r></w:p>")
    parts.append("<w:sectPr/></w:body></w:document>")
    return "".join(parts).encode("utf-8")


CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
""".strip().encode(
    "utf-8"
)

RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
""".strip().encode(
    "utf-8"
)

DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
</Relationships>
""".strip().encode(
    "utf-8"
)


def write_docx(path: Path, title: str, paragraphs: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", CONTENT_TYPES)
        zf.writestr("_rels/.rels", RELS)
        zf.writestr("word/document.xml", _document_xml(title, paragraphs))
        zf.writestr("word/_rels/document.xml.rels", DOC_RELS)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, title, paras in REPORTS:
        write_docx(OUT / name, title, paras)
        print("wrote", OUT / name)
    print(f"Done — {len(REPORTS)} files in {OUT}")


if __name__ == "__main__":
    main()
