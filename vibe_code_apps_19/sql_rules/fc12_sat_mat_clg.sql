-- fc12_sat_mat_clg.sql — FC12 SAT above MAT while cooling
WITH h AS (
  SELECT
    equipment_id,
    sat,
    mat,
    CASE WHEN oa_damper_pct IS NULL THEN NULL WHEN oa_damper_pct > 1.0 THEN oa_damper_pct / 100.0 ELSE oa_damper_pct END AS oa_damper_pct,
    CASE WHEN clg_valve_pct IS NULL THEN NULL WHEN clg_valve_pct > 1.0 THEN clg_valve_pct / 100.0 ELSE clg_valve_pct END AS clg_valve_pct
  FROM history
)
SELECT
  equipment_id,
  SUM(CASE
    WHEN sat IS NOT NULL AND mat IS NOT NULL AND clg_valve_pct > 0.01
     AND (sat - 1.15 - 0.55) > (mat + 1.15)
     AND (oa_damper_pct <= 0.05 OR oa_damper_pct > 0.9)
    THEN 1 ELSE 0 END) * {{POLL_SECONDS}} / 3600.0 AS fault_hours
FROM h
GROUP BY equipment_id;
