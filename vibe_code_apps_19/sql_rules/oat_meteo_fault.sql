-- oat_meteo_fault.sql — OAT hard-range proxy (weather wx_oa_t join deferred to next PR)
-- Flags BAS OAT outside physical envelope; full meteo compare needs wx_oa_t sidecar join.
SELECT
  equipment_id,
  SUM(CASE WHEN oa_t < -40.0 OR oa_t > 130.0 THEN 1 ELSE 0 END) * 300.0 / 3600.0 AS fault_hours,
  100.0 * SUM(CASE WHEN oa_t < -40.0 OR oa_t > 130.0 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) AS fault_pct
FROM history
WHERE oa_t IS NOT NULL
GROUP BY equipment_id;
