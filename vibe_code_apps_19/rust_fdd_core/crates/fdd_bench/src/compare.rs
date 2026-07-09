use std::path::Path;

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MetricRow {
    pub rule_id: Option<String>,
    pub equipment_id: Option<String>,
    pub metric: String,
    pub value: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct CompareMismatch {
    pub key: String,
    pub python_value: f64,
    pub sql_value: f64,
    pub delta: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct CompareReport {
    pub python_rows: usize,
    pub sql_rows: usize,
    pub matched: usize,
    pub mismatches: Vec<CompareMismatch>,
    pub material_failure: bool,
    pub tolerance: f64,
}

pub fn compare_results(
    python_path: &Path,
    sql_path: &Path,
    tolerance: f64,
) -> Result<CompareReport> {
    let py: Vec<MetricRow> = load_metrics(python_path)?;
    let sql: Vec<MetricRow> = load_metrics(sql_path)?;

    let mut matched = 0usize;
    let mut mismatches = Vec::new();

    for p in &py {
        let key = metric_key(p);
        if let Some(s) = sql.iter().find(|r| metric_key(r) == key) {
            let delta = (p.value - s.value).abs();
            if delta <= tolerance {
                matched += 1;
            } else {
                mismatches.push(CompareMismatch {
                    key: key.clone(),
                    python_value: p.value,
                    sql_value: s.value,
                    delta,
                });
            }
        }
    }

    let material_failure = !mismatches.is_empty() && !py.is_empty();

    Ok(CompareReport {
        python_rows: py.len(),
        sql_rows: sql.len(),
        matched,
        mismatches,
        material_failure,
        tolerance,
    })
}

fn metric_key(r: &MetricRow) -> String {
    format!(
        "{}|{}|{}",
        r.rule_id.as_deref().unwrap_or(""),
        r.equipment_id.as_deref().unwrap_or(""),
        r.metric
    )
}

fn load_metrics(path: &Path) -> Result<Vec<MetricRow>> {
    let text = std::fs::read_to_string(path).with_context(|| format!("read {}", path.display()))?;
    Ok(serde_json::from_str(&text)?)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use tempfile::NamedTempFile;

    #[test]
    fn compare_within_tolerance() {
        let mut py = NamedTempFile::new().unwrap();
        let mut sql = NamedTempFile::new().unwrap();
        let data = r#"[{"metric":"fan_hours","equipment_id":"AHU_1","value":10.0}]"#;
        write!(py, "{data}").unwrap();
        write!(
            sql,
            r#"[{{"metric":"fan_hours","equipment_id":"AHU_1","value":10.01}}]"#
        )
        .unwrap();
        let report = compare_results(py.path(), sql.path(), 0.1).unwrap();
        assert!(!report.material_failure);
    }
}
