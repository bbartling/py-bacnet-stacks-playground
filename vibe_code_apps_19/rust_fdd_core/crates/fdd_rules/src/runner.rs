use std::path::Path;

use anyhow::Result;
use datafusion::prelude::SessionContext;
use fdd_sql::{register_parquet_tree, run_sql_file};
use serde::Serialize;

use crate::registry::RuleRegistry;

#[derive(Debug, Clone, Serialize)]
pub struct RuleTiming {
    pub rule_id: String,
    pub row_count: usize,
    pub elapsed_ms: u128,
    pub output_path: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct RuleRunReport {
    pub rules_run: usize,
    pub rules_succeeded: usize,
    pub rules_failed: usize,
    pub timings: Vec<RuleTiming>,
    pub total_ms: u128,
}

pub async fn run_all_rules(
    parquet_root: &Path,
    registry: &RuleRegistry,
    out_dir: &Path,
) -> Result<RuleRunReport> {
    let started = std::time::Instant::now();
    std::fs::create_dir_all(out_dir)?;
    let ctx = SessionContext::new();
    register_parquet_tree(&ctx, parquet_root).await?;

    let mut timings = Vec::new();
    let mut rules_succeeded = 0usize;
    let mut rules_failed = 0usize;
    for rule in &registry.rules {
        let sql_path = Path::new(&registry.rules_dir).join(&rule.sql_file);
        let t0 = std::time::Instant::now();
        let out_path = out_dir.join(format!("{}.json", rule.rule_id));
        match run_sql_file(&ctx, &sql_path).await {
            Ok(result) => {
                std::fs::write(&out_path, serde_json::to_string_pretty(&result.rows)?)?;
                timings.push(RuleTiming {
                    rule_id: rule.rule_id.clone(),
                    row_count: result.row_count,
                    elapsed_ms: t0.elapsed().as_millis(),
                    output_path: out_path.display().to_string(),
                    error: None,
                });
                rules_succeeded += 1;
            }
            Err(e) => {
                timings.push(RuleTiming {
                    rule_id: rule.rule_id.clone(),
                    row_count: 0,
                    elapsed_ms: t0.elapsed().as_millis(),
                    output_path: out_path.display().to_string(),
                    error: Some(e.to_string()),
                });
                rules_failed += 1;
            }
        }
    }

    Ok(RuleRunReport {
        rules_run: timings.len(),
        rules_succeeded,
        rules_failed,
        timings,
        total_ms: started.elapsed().as_millis(),
    })
}
