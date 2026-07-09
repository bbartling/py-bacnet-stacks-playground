-- sat_high_fault.sql — FC13 SAT above SP at full cooling + confirm (matches cookbook fc13)
WITH h AS (
  SELECT
    equipment_id,
    timestamp_utc,
    sat,
    sat_sp,
    COALESCE(CASE WHEN clg_valve_pct IS NULL THEN NULL WHEN clg_valve_pct > 1.0 THEN clg_valve_pct / 100.0 ELSE clg_valve_pct END, 0.0) AS clg_valve_pct,
    COALESCE(CASE WHEN oa_damper_pct IS NULL THEN NULL WHEN oa_damper_pct > 1.0 THEN oa_damper_pct / 100.0 ELSE oa_damper_pct END, 0.0) AS oa_damper_pct
  FROM history
),
base AS (
  SELECT
    equipment_id,
    timestamp_utc,
    CAST(CASE
      WHEN sat IS NOT NULL AND sat_sp IS NOT NULL
       AND clg_valve_pct > 0.01
       AND sat > sat_sp + 1.0
       AND (oa_damper_pct <= 0.05 OR oa_damper_pct > 0.9)
      THEN 1 ELSE 0 END AS INT) AS raw_fault
  FROM h
),
grp AS (
  SELECT
    *,
    SUM(CASE WHEN raw_fault = 0 THEN 1 ELSE 0 END)
      OVER (PARTITION BY equipment_id ORDER BY timestamp_utc ROWS UNBOUNDED PRECEDING) AS streak_id
  FROM base
),
ranked AS (
  SELECT
    *,
    ROW_NUMBER() OVER (PARTITION BY equipment_id, streak_id ORDER BY timestamp_utc) AS streak_len
  FROM grp
),
final AS (
  SELECT
    equipment_id,
    CASE WHEN raw_fault = 1 AND streak_len >= {{CONFIRM_ROWS}} THEN 1 ELSE 0 END AS confirmed
  FROM ranked
)
SELECT
  equipment_id,
  SUM(confirmed) * {{POLL_SECONDS}} / 3600.0 AS fault_hours
FROM final
GROUP BY equipment_id;
