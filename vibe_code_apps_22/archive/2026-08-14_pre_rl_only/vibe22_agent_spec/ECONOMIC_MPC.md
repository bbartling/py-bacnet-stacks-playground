# Economic MPC screening (agent supervisor)

**Surface:** `scripts/vibe22.py` (Streamlit REMOVED) +
`eplus_gym/optimize/six_zone_study.py`.

**Claim label:** ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY.

## Boundaries

- Agents may launch studies and write proposal artifacts under
  `reports/eplus_gym/optimization/<study_id>/`.
- **Approve** writes `approved_recommendation.json` only.
- Do **not** auto-write Site Config, `last_dsm_run.json`, ECM compare, champion IDF, or BACnet.
- Default money mode: `PHYSICAL_ONLY` (billing-floor math still shown; $ do not pick winners).
- Six-zone DualSP actuation must PASS `scripts/gate_six_zone_actuation.py` first.
- Legacy opt-start iteration skill/script is INVALID.

See `skills/eplus-economic-mpc/SKILL.md`.
