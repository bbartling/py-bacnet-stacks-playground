# full_evaluation vs smoke (post contract fix)

**Generated:** 2026-08-10 10:01:37Z
**Source:** `train_four_arms.py --profile full_evaluation --jobs 4` (watched terminal 1)

## Smoke (earlier today, max_days=14)

| Arm | peak_mae_kw | zone_mae | n_days (index) |
|---|---|---|---|
| sklearn_allyear | 20.04 | 0.34 | 36 |
| sklearn_winter | 36.99 | 1.10 | 36 |
| torch_allyear | 21.06 | 0.43 | 36 |
| torch_winter | 31.04 | 1.00 | 36 |

## full_evaluation

profile=`full_evaluation` wall_seconds=5398.405461600007

| Arm | ok | peak_mae_kw | zone_mae | n_days | champion/family |
|---|---|---|---|---|---|
| sklearn_allyear | True | 30.741901482787632 | 1.3626344048362573 | 335 | gradient_boosting |
| sklearn_winter | True | 35.76211257899166 | 1.1555069437020438 | 152 | extra_trees |
| torch_allyear | True | 38.759850780312654 | 1.9463939274618853 | 335 | resmlp_dualhead |
| torch_winter | True | 69.02749202919073 | 2.6605830803081276 | 152 | resmlp_dualhead |

## Recommendation

- Honesty: `HYBRID_SCREENING` — **do not promote** solely because scores moved after contract fix.
- Next: grey-box Wave 1 (sensor manifest + 1R1C) per `greybox_shadow_v1_path` plan — no extra `train_four_arms` required for grey-box.
