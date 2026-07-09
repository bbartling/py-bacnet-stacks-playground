//! Rule registry and DataFusion SQL batch runner.

pub mod registry;
pub mod runner;

pub use registry::{load_registry, RuleRegistry};
pub use runner::{run_all_rules, RuleRunReport};
