-- fan_runtime_hours.sql
-- Fan runtime hours: fan_cmd normalized > 0.05
-- Input: Parquet history table per equipment (registered as equipment_id)
-- Output: equipment_id, fan_runtime_hours, total_hours (poll=300s default)

SELECT
  equipment_id,
  SUM(CASE WHEN fan_cmd > 0.05 THEN 1 ELSE 0 END) * 300.0 / 3600.0 AS fan_runtime_hours,
  COUNT(*) * 300.0 / 3600.0 AS total_hours
FROM history
WHERE fan_cmd IS NOT NULL
GROUP BY equipment_id;
