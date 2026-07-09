-- fc9_oa_sat_sp_econ.sql — FC9 OAT high vs SAT SP while economizing
WITH h AS (
  SELECT
    equipment_id,
    oa_t,
    COALESCE(sat_sp, 55.0) AS sat_sp,
    CASE WHEN oa_damper_pct IS NULL THEN NULL WHEN oa_damper_pct > 1.0 THEN oa_damper_pct / 100.0 ELSE oa_damper_pct END AS oa_damper_pct,
    CASE WHEN clg_valve_pct IS NULL THEN NULL WHEN clg_valve_pct > 1.0 THEN clg_valve_pct / 100.0 ELSE clg_valve_pct END AS clg_valve_pct
  FROM history
)
SELECT
  equipment_id,
  SUM(CASE
    WHEN oa_t IS NOT NULL AND sat_sp IS NOT NULL
     AND oa_damper_pct > 0.05 AND clg_valve_pct < 0.1
     AND (oa_t - 1.15) > (sat_sp - 0.55 + 1.15)
    THEN 1 ELSE 0 END) * {{POLL_SECONDS}} / 3600.0 AS fault_hours
FROM h
GROUP BY equipment_id;
