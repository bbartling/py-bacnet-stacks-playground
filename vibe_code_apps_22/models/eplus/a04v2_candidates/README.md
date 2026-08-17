# A04-v2 candidate IDFs are regenerated, not committed

Generated `*.idf` files under this directory are **not** git-tracked. Rebuild
them from immutable parent A04 plus the committed `parameters.json` in each
folder.

Parent: `models/eplus/lakeside_w2a_a04_dual_champion.idf`

```powershell
# Stage A CapMult / InternalMass one-factor children
python scripts/a04v2_build_capmult_candidate.py --temp-mult 28 --run-id capmult_t28

# Stage B multivariable children
python scripts/a04v2_build_stage_b_candidate.py --plant autosize_htg --capmult 12 --mass-m2 0 --run-id sb_autosizehtg_c12_m0_20260112
```

Raw EnergyPlus run packs belong in `SITE_ROOT` (or another artifact store), not
this repository. Do not treat leftover local smoke trees (for example
`smoke_plant_autosize/`) as a champion.
