use std::path::Path;

use anyhow::Result;
use datafusion::prelude::SessionContext;
use fdd_sql::{register_parquet_tree, register_weather_if_present, run_sql};
use serde::Serialize;

use crate::params::{read_poll_from_cache, rule_params, substitute_sql};
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
    pub poll_seconds: f64,
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
    let poll_seconds = read_poll_from_cache(parquet_root).unwrap_or(300.0);

    let ctx = SessionContext::new();
    register_parquet_tree(&ctx, parquet_root).await?;
    register_weather_if_present(&ctx, parquet_root).await?;

    let mut timings = Vec::new();
    let mut rules_succeeded = 0usize;
    let mut rules_failed = 0usize;
    for rule in &registry.rules {
        let sql_path = Path::new(&registry.rules_dir).join(&rule.sql_file);
        let t0 = std::time::Instant::now();
        let out_path = out_dir.join(format!("{}.json", rule.rule_id));
        let raw_sql = match std::fs::read_to_string(&sql_path) {
            Ok(s) => s,
            Err(e) => {
                timings.push(RuleTiming {
                    rule_id: rule.rule_id.clone(),
                    row_count: 0,
                    elapsed_ms: t0.elapsed().as_millis(),
                    output_path: out_path.display().to_string(),
                    error: Some(e.to_string()),
                });
                rules_failed += 1;
                continue;
            }
        };
        let sql = substitute_sql(&raw_sql, &rule_params(poll_seconds, rule.confirm_seconds));
        match run_sql(&ctx, &sql).await {
            Ok(result) => {
                std::fs::write(
                    &out_path,
                    serde_json::to_string_pretty(&serde_json::json!({"rows": result.rows}))?,
                )?;
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
                let err_body = serde_json::json!({"rows": [], "error": e.to_string()});
                let _ = std::fs::write(&out_path, serde_json::to_string_pretty(&err_body)?);
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
        poll_seconds,
        timings,
        total_ms: started.elapsed().as_millis(),
    })
}
