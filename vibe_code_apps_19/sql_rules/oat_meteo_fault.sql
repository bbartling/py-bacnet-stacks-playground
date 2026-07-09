-- oat_meteo_fault.sql — BAS OAT vs weather reference (|Δ| > 5°F) + confirm
-- Requires weather Parquet sidecar (`weather` table). Falls back to zero rows if absent.
WITH wx AS (
  SELECT timestamp_utc, oa_t AS wx_oa_t FROM weather WHERE oa_t IS NOT NULL
),
joined AS (
  SELECT
    h.equipment_id,
    h.timestamp_utc,
    h.oa_t,
    wx.wx_oa_t
  FROM history h
  INNER JOIN wx ON h.timestamp_utc = wx.timestamp_utc
  WHERE h.oa_t IS NOT NULL
    AND (h.equipment_id LIKE 'AHU%' OR h.equipment_id LIKE 'AHU_%')
),
base AS (
  SELECT
    equipment_id,
    timestamp_utc,
    CAST(CASE WHEN ABS(oa_t - wx_oa_t) > 5.0 THEN 1 ELSE 0 END AS INT) AS raw_fault
  FROM joined
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
  SUM(confirmed) * {{POLL_SECONDS}} / 3600.0 AS fault_hours,
  100.0 * SUM(confirmed) / NULLIF(COUNT(*), 0) AS fault_pct
FROM final
GROUP BY equipment_id;
