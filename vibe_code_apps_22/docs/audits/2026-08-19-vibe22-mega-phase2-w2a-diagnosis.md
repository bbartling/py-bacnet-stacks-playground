# Vibe22 mega Phase 2 — W2A diagnosis (hypothesis)

**Conclusion strength:** `LEADING_ROOT_CAUSE_HYPOTHESIS`

Machine-readable: [`phase2_w2a_diagnosis.json`](figures/vibe22_mega_phase2/phase2_w2a_diagnosis.json)

## Leading hypothesis

LEADING_ROOT_CAUSE_HYPOTHESIS: identical 149430 W rated heating on all nine aggregated WAHP coils with autosized airflow likely drives chronic part-load airflow fraction below 25% of rated — pending live child-model confirmation.

## MCP tools invoked

- `load_idf_model` — payload SHA256 `c415f0ec070357a0…`
- `get_model_summary` — payload SHA256 `b062b4044979731f…`
- `discover_hvac_loops` — payload SHA256 `cd6e1045d4cf3ecc…`

## Hypothesis ledger

### H1_identical_hardcoded_heating (primary)
- **Objects:** `Coil:Heating:WaterToAirHeatPump:EquationFit, * WAHP Heating Coil`
- **Evidence:** All nine heating coils hard-coded to 149430 W (87900×1.70 A04 dial) regardless of zone HP inventory (2–13 HP per zone).

### H2_autosized_airflow_vs_part_load (primary)
- **Objects:** `Rated Air Flow Rate = Autosize on all W2A coils and fans`
- **Evidence:** Rated airflow autosized against identical 149430 W capacity; historical ERR shows millions of recurring low-airflow prints at scored runtime (Phase 1 freeze).
- **Forbidden fix:** Do not shrink rated airflow alone to silence warnings.

### H3_hp_count_contract_mismatch (secondary)
- **Objects:** `contracts/eplus_nine_to_six_zone_agg_v1.json default_hp_counts`
- **Evidence:** BAS split sums to 67 HP; agg v1 sums to 79.

### H4_equationfit_wide_curve_domain (monitor)
- **Objects:** `Curve:QuadLinear * HtgCapCurve`
- **Evidence:** Performance curves allow wide w/x/y/z domains — extrapolation risk.

## Nine-zone unit table

| Zone | ZoneHVAC | Heating coil | Rated htg W | Rated airflow | HP count |
| --- | --- | --- | ---: | --- | ---: |
| 1F_Library_IMC | `1F_Library_IMC WAHP` | `1F_Library_IMC WAHP Heating Coil` | 149430.0 | autosize | 2 |
| 1F_Cafe_Kitchen | `1F_Cafe_Kitchen WAHP` | `1F_Cafe_Kitchen WAHP Heating Coil` | 149430.0 | autosize | 3 |
| 1F_Gym | `1F_Gym WAHP` | `1F_Gym WAHP Heating Coil` | 149430.0 | autosize | 4 |
| 1F_Area_A | `1F_Area_A WAHP` | `1F_Area_A WAHP Heating Coil` | 149430.0 | autosize | 13 |
| 1F_Area_B | `1F_Area_B WAHP` | `1F_Area_B WAHP Heating Coil` | 149430.0 | autosize | 10 |
| 1F_Area_C | `1F_Area_C WAHP` | `1F_Area_C WAHP Heating Coil` | 149430.0 | autosize | 8 |
| 1F_Area_D | `1F_Area_D WAHP` | `1F_Area_D WAHP Heating Coil` | 149430.0 | autosize | 6 |
| 2F_Area_A | `2F_Area_A WAHP` | `2F_Area_A WAHP Heating Coil` | 149430.0 | autosize | 11 |
| 2F_Area_B | `2F_Area_B WAHP` | `2F_Area_B WAHP Heating Coil` | 149430.0 | autosize | 10 |

*No model edits in Phase 2. Not a proven root cause until child-model runtime confirms. BACnet command authority = 0. Vibe19 untouched.*
