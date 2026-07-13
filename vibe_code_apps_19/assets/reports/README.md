# Prebuilt Word reports

The Streamlit app **does not generate** DOCX at runtime. It serves the `.docx` files
in this folder via download buttons.

## Hierarchy

1. **Mechanical family (primary)** — on **RCx Plots**, pick Zones/AHU/Boiler/Chiller/Heat pump/Metering/Weather → **Download … RCx Word Template**
2. **Universal Finding Sheet** / **Portfolio Executive Report** — secondary on that tab
3. **Complete ZIP pack** — on **Export**: `Open-FDD_Vibe19_RCx_DOCX_Template_Pack.zip`

## Filenames

| File | Where |
| --- | --- |
| `rcx_ahu_air.docx` … family files | RCx Plots (by family) + Export expander |
| `rcx_heat_pump.docx`, `rcx_weather.docx` | Template-only RCx families |
| `rcx_universal_finding_sheet.docx` | Secondary on RCx + Export |
| `rcx_portfolio_executive.docx` | Secondary on RCx + Export |
| `rcx_catalog.docx`, `analytics.docx`, `data_model.docx` | Export expander + ZIP |
| `fdd_*.docx` | FDD Plots (by device type) |
| `Open-FDD_Vibe19_RCx_DOCX_Template_Pack.zip` | Export (primary pack download) |

Overwrite any file in place with your edited Word doc (keep the name). Rebuild/pull Docker after replacing.
