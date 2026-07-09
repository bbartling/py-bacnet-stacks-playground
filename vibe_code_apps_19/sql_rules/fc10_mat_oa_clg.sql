-- fc10_mat_oa_clg.sql — FC10 MAT-OAT delta while cooling + economizing
WITH h AS (
  SELECT
    equipment_id,
    mat,
    oa_t,
    CASE WHEN oa_damper_pct IS NULL THEN NULL WHEN oa_damper_pct > 1.0 THEN oa_damper_pct / 100.0 ELSE oa_damper_pct END AS oa_damper_pct,
    CASE WHEN clg_valve_pct IS NULL THEN NULL WHEN clg_valve_pct > 1.0 THEN clg_valve_pct / 100.0 ELSE clg_valve_pct END AS clg_valve_pct
  FROM history
)
SELECT
  equipment_id,
  SUM(CASE
    WHEN mat IS NOT NULL AND oa_t IS NOT NULL
     AND clg_valve_pct > 0.01 AND oa_damper_pct > 0.9
     AND ABS(mat - oa_t) > SQRT(1.15 * 1.15 + 1.15 * 1.15)
    THEN 1 ELSE 0 END) * {{POLL_SECONDS}} / 3600.0 AS fault_hours
FROM h
GROUP BY equipment_id;
