# P0 Integrity inventory — tip 722d01c (2026-08-06)
# Do not hand-edit metrics; regenerate via notebook after code fixes.

| Artifact | sha256[:16] | Invalid evidence |
|---|---|---|
| real_baseline_15min_v1_model_card.json | ee83ae9f75e5d02f | 2-day heldout backfill (not chrono manifest) |
| eplus_delta_15min_v1_model_card.json | be4dea07dcff4f7e | provisional_from_teacher_forced_until_notebook_retrain |
| hybrid_ship_manifest.json | 7ddc78ff0bad4445 | embeds provisional delta heldout note |
| real_baseline_15min_v1.onnx | 55566a08bb5f083e | — |
| eplus_delta_15min_v1.onnx | 3043ecc71b9300c1 | — |

Purge path: regenerate cards via clean-kernel notebook Run All after chrono/control/promote code lands.
