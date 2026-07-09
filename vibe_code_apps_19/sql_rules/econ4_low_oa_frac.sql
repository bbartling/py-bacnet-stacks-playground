-- econ4_low_oa_frac.sql — ECON-4 low estimated OA fraction
WITH h AS (
  SELECT
    equipment_id,
    mat,
    rat,
    oa_t,
    CASE WHEN fan_cmd IS NULL THEN NULL WHEN fan_cmd > 1.0 THEN fan_cmd / 100.0 ELSE fan_cmd END AS fan_cmd
  FROM history
)
SELECT
  equipment_id,
  SUM(CASE
    WHEN fan_cmd > 0.01 AND mat IS NOT NULL AND rat IS NOT NULL AND oa_t IS NOT NULL
     AND ABS(rat - oa_t) > 2.2
     AND ((mat - rat) / NULLIF(oa_t - rat, 0)) * 100.0 < 21.0
    THEN 1 ELSE 0 END) * {{POLL_SECONDS}} / 3600.0 AS fault_hours
FROM h
GROUP BY equipment_id;
