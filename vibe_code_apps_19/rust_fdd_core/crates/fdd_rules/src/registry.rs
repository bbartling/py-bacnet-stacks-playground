use std::path::Path;

use anyhow::{Context, Result};
use fdd_core::RuleDefinition;
use serde::Deserialize;

#[derive(Debug, Deserialize)]
struct RegistryFile {
    rules: Vec<RuleEntry>,
}

#[derive(Debug, Deserialize)]
struct RuleEntry {
    rule_id: String,
    sql_file: String,
    description: String,
    #[serde(default)]
    required_roles: Vec<String>,
    #[serde(default)]
    output_columns: Vec<String>,
    #[serde(default = "default_confirm")]
    confirm_seconds: u32,
}

fn default_confirm() -> u32 {
    300
}

#[derive(Debug, Clone)]
pub struct RuleRegistry {
    pub rules_dir: String,
    pub rules: Vec<RuleDefinition>,
}

pub fn load_registry(rules_dir: &Path) -> Result<RuleRegistry> {
    let manifest = rules_dir.join("registry.yaml");
    let text = std::fs::read_to_string(&manifest)
        .with_context(|| format!("read {}", manifest.display()))?;
    let parsed: RegistryFile = serde_yaml::from_str(&text)?;
    let rules = parsed
        .rules
        .into_iter()
        .map(|r| RuleDefinition {
            rule_id: r.rule_id,
            sql_file: r.sql_file,
            description: r.description,
            required_roles: r.required_roles,
            output_columns: r.output_columns,
            confirm_seconds: r.confirm_seconds,
        })
        .collect();
    Ok(RuleRegistry {
        rules_dir: rules_dir.display().to_string(),
        rules,
    })
}
