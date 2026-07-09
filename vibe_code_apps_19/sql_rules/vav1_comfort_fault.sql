-- vav1_comfort_fault.sql — zone comfort band (default 68-76 F)
SELECT
  equipment_id,
  SUM(CASE WHEN zone_t < 68.0 OR zone_t > 76.0 THEN 1 ELSE 0 END) * 300.0 / 3600.0 AS fault_hours,
  100.0 * SUM(CASE WHEN zone_t < 68.0 OR zone_t > 76.0 THEN 1 ELSE 0 END) / COUNT(*) AS fault_pct
FROM history
WHERE zone_t IS NOT NULL
GROUP BY equipment_id;
