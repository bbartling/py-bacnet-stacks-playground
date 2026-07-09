-- fc2_mat_low.sql — FC2 mixed air below envelope + confirm
WITH h AS (
  SELECT equipment_id, timestamp_utc, mat, oa_t, rat,
    CASE WHEN fan_cmd IS NULL THEN NULL WHEN fan_cmd > 1.0 THEN fan_cmd / 100.0 ELSE fan_cmd END AS fan_cmd
  FROM history
),
base AS (
  SELECT equipment_id, timestamp_utc,
    CAST(CASE WHEN fan_cmd > 0.01 AND mat IS NOT NULL AND oa_t IS NOT NULL AND rat IS NOT NULL
      AND (mat - 1.15) < (rat - 1.15) AND (mat - 1.15) < (oa_t - 1.15) THEN 1 ELSE 0 END AS INT) AS raw_fault
  FROM h
),
grp AS (
  SELECT *, SUM(CASE WHEN raw_fault = 0 THEN 1 ELSE 0 END)
    OVER (PARTITION BY equipment_id ORDER BY timestamp_utc ROWS UNBOUNDED PRECEDING) AS streak_id
  FROM base
),
ranked AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY equipment_id, streak_id ORDER BY timestamp_utc) AS streak_len FROM grp
),
final AS (
  SELECT equipment_id, CASE WHEN raw_fault = 1 AND streak_len >= {{CONFIRM_ROWS}} THEN 1 ELSE 0 END AS confirmed FROM ranked
)
SELECT equipment_id, SUM(confirmed) * {{POLL_SECONDS}} / 3600.0 AS fault_hours FROM final GROUP BY equipment_id;
