-- fc7_sat_low_heating.sql — FC7 SAT low while heating at full
WITH h AS (
  SELECT
    equipment_id,
    sat,
    COALESCE(sat_sp, 55.0) AS sat_sp,
    CASE WHEN fan_cmd IS NULL THEN NULL WHEN fan_cmd > 1.0 THEN fan_cmd / 100.0 ELSE fan_cmd END AS fan_cmd,
    CASE WHEN htg_valve_pct IS NULL THEN NULL WHEN htg_valve_pct > 1.0 THEN htg_valve_pct / 100.0 ELSE htg_valve_pct END AS htg_valve_pct
  FROM history
)
SELECT
  equipment_id,
  SUM(CASE
    WHEN sat IS NOT NULL AND sat_sp IS NOT NULL AND fan_cmd > 0.01
     AND sat < sat_sp - 1.0 AND htg_valve_pct > 0.9
    THEN 1 ELSE 0 END) * {{POLL_SECONDS}} / 3600.0 AS fault_hours
FROM h
GROUP BY equipment_id;
