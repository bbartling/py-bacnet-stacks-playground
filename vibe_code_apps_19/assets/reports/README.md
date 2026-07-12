# Prebuilt Word reports

The Streamlit app **does not generate** DOCX at runtime. It serves the `.docx` files
in this folder via download buttons (FDD by equipment type, RCx by mechanical family,
plus data-model / analytics stubs on Export).

## Replace dummies

1. Open or create your real Word report.
2. Save/overwrite the matching filename here (keep the same name).
3. Redeploy / rebuild the Docker image so the new bytes ship with the app.

| File | Served from |
| --- | --- |
| `fdd_ahu.docx` … `fdd_*.docx` | **FDD Plots** → Download FDD DOCX (by device type) |
| `rcx_zones_vav.docx` … | **RCx Plots** → Download for selected mechanical family |
| `rcx_catalog.docx` | **Export** → RCx catalog |
| `data_model.docx` | **Data Model** + **Export** |
| `analytics.docx` | **Export** |

Regenerate placeholder shells only: `python scripts/gen_dummy_docx_reports.py`
