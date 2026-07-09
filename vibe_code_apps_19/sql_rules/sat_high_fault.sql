-- sat_high_fault.sql — FC13-style SAT high at full cooling
-- BUILDING_100 lacks sat_sp column; uses 55°F reference until sat_sp role mapping exists.
SELECT
  equipment_id,
  SUM(CASE WHEN sat > 55.0 AND clg_valve_pct > 0.9 THEN 1 ELSE 0 END) * 300.0 / 3600.0 AS fault_hours
FROM history
WHERE sat IS NOT NULL AND clg_valve_pct IS NOT NULL
GROUP BY equipment_id;
