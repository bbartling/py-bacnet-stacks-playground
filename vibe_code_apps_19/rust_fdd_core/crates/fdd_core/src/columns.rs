use std::collections::HashMap;
use std::path::Path;

use crate::error::Result;

/// Map physical CSV column name → cookbook logical role used by SQL rules.
pub fn load_column_role_map(path: &Path) -> Result<HashMap<String, String>> {
    let mut out = HashMap::new();
    let mut rdr = csv::Reader::from_path(path)?;
    let headers = rdr.headers()?.clone();
    let col_idx = header_index(&headers, &["col", "column"]);
    let role_idx = header_index(&headers, &["point_role", "role"]);
    if col_idx.is_none() {
        return Ok(out);
    }
    let col_idx = col_idx.unwrap();

    for rec in rdr.records() {
        let rec = rec?;
        let column = rec.get(col_idx).unwrap_or("").trim().to_string();
        if column.is_empty() || column == "col" || column == "column" {
            continue;
        }
        let raw_role = role_idx.and_then(|i| rec.get(i)).unwrap_or("").trim();
        let role = if raw_role.is_empty() || raw_role == "ahu_point" {
            infer_role_from_column_name(&column)
        } else {
            Some(normalize_role(raw_role))
        };
        let Some(role) = role else { continue };
        if role == "ahu_point" || role == "ignore" {
            continue;
        }
        // Prefer first mapping per role (supply fan before return fan, etc.)
        out.entry(column).or_insert(role);
    }
    Ok(out)
}

fn header_index(headers: &csv::StringRecord, names: &[&str]) -> Option<usize> {
    for (i, h) in headers.iter().enumerate() {
        let hl = h.trim().to_lowercase();
        if names.iter().any(|n| hl == *n) {
            return Some(i);
        }
    }
    None
}

/// Align columns.csv / Haystack role strings with SQL rule column names.
pub fn normalize_role(role: &str) -> String {
    match role.trim().to_lowercase().as_str() {
        "oat" | "outside_air_temp" | "outside_air_temp_f" | "oa_t" => "oa_t".into(),
        "zone_temp" | "zone_temperature" | "zn_t" | "zone_t" => "zone_t".into(),
        "supply_air_temp" | "supply_air_temperature" | "discharge_air_temp" | "sat" => "sat".into(),
        "return_air_temp" | "rat" => "rat".into(),
        "mixed_air_temp" | "mat" => "mat".into(),
        "fan_speed" | "fan_pct" | "fan_percent" | "fan_status" | "fan_cmd" | "supply_fan"
        | "return_fan" => "fan_cmd".into(),
        "oa_damper" | "outside_air_damper" | "damper" | "oa_damper_pct" => "oa_damper_pct".into(),
        "cooling_valve" | "clg_valve" | "chw_valve" => "clg_valve_pct".into(),
        "heating_valve" | "htg_valve" => "htg_valve_pct".into(),
        "sat_setpoint" | "sat_sp" => "sat_sp".into(),
        other => other.to_string(),
    }
}

fn infer_role_from_column_name(column: &str) -> Option<String> {
    let c = column.to_lowercase();
    if c.contains("supply_fan_speed")
        || c == "supplyfan"
        || c.ends_with("sf-c")
        || c.contains("sf_s")
    {
        return Some("fan_cmd".into());
    }
    if c.contains("outside_air_temp") || c.contains("oa_t") || c.ends_with("oa-t") {
        return Some("oa_t".into());
    }
    if c.contains("discharge_air") || c.starts_with("dat_") || c.contains(" da-t") {
        return Some("sat".into());
    }
    if c.contains("return_air") || c.contains("ra_t") || c.contains("ra-t") {
        return Some("rat".into());
    }
    if c.contains("mixed_air") || c.contains("ma_t") || c.contains("ma-t") || c == "mad_c" {
        return Some("mat".into());
    }
    if c.contains("chw_valve") || c.contains("clg_valve") {
        return Some("clg_valve_pct".into());
    }
    if c.contains("damper") || c.contains("dmpr") || c.contains("mad_c") {
        return Some("oa_damper_pct".into());
    }
    if c.contains("zone_t") || c.contains("space_temp") || c.contains("spacetemp") {
        return Some("zone_t".into());
    }
    if c.contains("sat_sp") || c.contains("sat_setpoint") {
        return Some("sat_sp".into());
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use tempfile::TempDir;

    #[test]
    fn normalize_oat_alias() {
        assert_eq!(normalize_role("outside_air_temp"), "oa_t");
        assert_eq!(normalize_role("supply_fan"), "fan_cmd");
    }

    #[test]
    fn load_building_style_columns_csv() {
        let tmp = TempDir::new().unwrap();
        let path = tmp.path().join("columns.csv");
        let mut f = std::fs::File::create(&path).unwrap();
        writeln!(
            f,
            "col,point_name,unit,point_role,vav_id\n\
             supply_fan_speed_pct,SF-VFD,%,supply_fan,\n\
             outside_air_temp_f,OA-T,°F,outside_air_temp,\n\
             zone_t100_x,bld SpaceTemp,°F,zone_temp,VAV_1"
        )
        .unwrap();
        let map = load_column_role_map(&path).unwrap();
        assert_eq!(
            map.get("supply_fan_speed_pct"),
            Some(&"fan_cmd".to_string())
        );
        assert_eq!(map.get("outside_air_temp_f"), Some(&"oa_t".to_string()));
        assert_eq!(map.get("zone_t100_x"), Some(&"zone_t".to_string()));
    }
}
