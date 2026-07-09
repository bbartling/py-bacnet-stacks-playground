-- economizer_fault.sql — ECON-2 proxy: high OA damper when OAT > 75 F
SELECT
  equipment_id,
  SUM(CASE WHEN oa_t > 75.0 AND oa_damper_pct > 0.2 THEN 1 ELSE 0 END) * 300.0 / 3600.0 AS fault_hours
FROM history
WHERE oa_t IS NOT NULL AND oa_damper_pct IS NOT NULL
GROUP BY equipment_id;
