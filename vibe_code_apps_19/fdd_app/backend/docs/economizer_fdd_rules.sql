-- AHU Economizer FDD — DataFusion SQL rule templates
-- Run against Arrow/Feather time-series tables with logical column names.
-- Parameters: @poll_seconds, @confirm_samples, @temp_db, @damper_db, @oat_favorable_delta

WITH base_clean AS (
  SELECT
    ahu_id,
    timestamp,
    fan_cmd_pct / 100.0 AS fan_pct,
    oat_f, rat_f, mat_f, sat_f, sat_sp_f,
    oa_damper_cmd_pct / 100.0 AS oad_cmd,
    COALESCE(oa_damper_pos_pct, oa_damper_cmd_pct) / 100.0 AS oad_pos,
    COALESCE(oa_min_pct, 15) / 100.0 AS oad_min,
    cooling_cmd_pct / 100.0 AS clg,
    LAG(timestamp) OVER (PARTITION BY ahu_id ORDER BY timestamp) AS prev_ts
  FROM ahu_timeseries
  WHERE timestamp IS NOT NULL
),

stable_ahu_operation AS (
  SELECT *,
    fan_pct > 0.05 AS fan_on,
    EXTRACT(EPOCH FROM (timestamp - prev_ts)) <= @poll_seconds * 4 AS no_gap,
    -- occupied schedule: Mon-Fri 6-17, Sat 7-14 local (precompute occupied flag in ETL if needed)
    occupied AS is_occupied,
    fan_on AND occupied AND no_gap AS stable
  FROM base_clean
),

economizer_suitability AS (
  SELECT *,
    stable AND oat_f BETWEEN @econ_low_f AND @econ_high_f
      AND (rat_f - oat_f) > @oat_favorable_delta AS econ_suitable_drybulb,
    stable AND (
      sat_f > sat_sp_f + @temp_db OR clg > 0.20
    ) AS cooling_load
  FROM stable_ahu_operation
),

sensor_plausibility AS (
  SELECT *,
    stable AND (
      mat_f < LEAST(oat_f, rat_f) - @mat_db
      OR mat_f > GREATEST(oat_f, rat_f) + @mat_db
    ) AS mat_implausible,
    CASE
      WHEN ABS(oat_f - rat_f) > @oat_rat_min_delta
      THEN LEAST(GREATEST((mat_f - rat_f) / NULLIF(oat_f - rat_f, 0), 0), 1)
      ELSE NULL
    END AS oa_fraction_est
  FROM economizer_suitability
),

damper_response AS (
  SELECT *,
    econ_suitable_drybulb AND cooling_load AS econ_should_enable,
    econ_suitable_drybulb AND clg > 0.20 AND oad_pos < 0.85 AS mech_cool_free_cool_avail
  FROM sensor_plausibility
),

fault_windows AS (
  SELECT *,
    -- ECON_NOT_ECONOMIZING_WHEN_SHOULD
    econ_should_enable AND oad_pos < oad_min + @damper_db / 100.0 AND NOT mat_implausible
      AS raw_not_economizing,
    -- ECON_ECONOMIZING_WHEN_SHOULD_NOT
    stable AND NOT econ_suitable_drybulb
      AND oad_pos > oad_min + @damper_db / 100.0
      AND (oat_f > @econ_high_f OR oat_f < @econ_low_f)
      AS raw_econ_when_not,
    -- ECON_MECH_COOLING_DURING_FREE_COOLING
    mech_cool_free_cool_avail AND NOT mat_implausible AS raw_mech_free_cool,
    -- ECON_MAT_PLAUSIBILITY
    mat_implausible AS raw_mat_plausibility,
    -- ECON_EXCESS_OA
    stable AND NOT econ_suitable_drybulb
      AND oad_pos > oad_min + @damper_db / 100.0 AS raw_excess_oa,
    -- ECON_LOW_OA_VENTILATION_RISK
    stable AND oad_pos < oad_min - @damper_db / 100.0 AS raw_low_oa
  FROM damper_response
),

-- Persistence: apply rolling SUM >= @confirm_samples in application layer or window functions
fault_rollups AS (
  SELECT
    ahu_id,
    'ECON_NOT_ECONOMIZING_WHEN_SHOULD' AS fault_code,
    SUM(CASE WHEN raw_not_economizing THEN 1 ELSE 0 END) AS affected_samples,
    SUM(CASE WHEN raw_not_economizing THEN @poll_seconds ELSE 0 END) / 60.0 AS total_fault_minutes
  FROM fault_windows
  GROUP BY ahu_id
  UNION ALL
  SELECT ahu_id, 'ECON_MECH_COOLING_DURING_FREE_COOLING',
    SUM(CASE WHEN raw_mech_free_cool THEN 1 ELSE 0 END),
    SUM(CASE WHEN raw_mech_free_cool THEN @poll_seconds ELSE 0 END) / 60.0
  FROM fault_windows GROUP BY ahu_id
  UNION ALL
  SELECT ahu_id, 'ECON_MAT_PLAUSIBILITY',
    SUM(CASE WHEN raw_mat_plausibility THEN 1 ELSE 0 END),
    SUM(CASE WHEN raw_mat_plausibility THEN @poll_seconds ELSE 0 END) / 60.0
  FROM fault_windows GROUP BY ahu_id
)

SELECT * FROM fault_rollups ORDER BY ahu_id, fault_code;
