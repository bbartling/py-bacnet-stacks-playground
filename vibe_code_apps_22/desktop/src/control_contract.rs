//! Farm-SoT control strategy fixtures (`contracts/control_strategies_v1`).
//!
//! Desktop loads fixed 96-step schedules — PRBS arms are farm-only.

use std::path::{Path, PathBuf};

use anyhow::{bail, Context, Result};
use serde::Deserialize;

use crate::features_15min::{HP_ON_COLS, OCC_FRAC_COLS, STEPS_96};

const CONTRACT_VERSION: &str = "control_strategies_v1";

/// One 15-min control step: per-zone occ/hp plus schedule knobs.
#[derive(Debug, Clone)]
pub struct ControlStep {
    pub occ: [f32; 6],
    pub hp: [f32; 6],
    pub preheat_lead_h: f32,
    pub stagger_min: f32,
    pub unocc_htg_sp_f: f32,
    pub occ_htg_sp_f: f32,
}

/// Full 96-step control schedule for one strategy_id.
#[derive(Debug, Clone)]
pub struct ControlSchedule {
    pub strategy_id: String,
    pub steps: Vec<ControlStep>,
}

#[derive(Debug, Deserialize)]
struct FixtureDoc {
    contract_version: String,
    strategy_id: String,
    steps: Vec<FixtureStep>,
}

#[derive(Debug, Deserialize)]
#[allow(non_snake_case)] // field names match farm-SoT JSON (occ_frac_1F_A, …)
struct FixtureStep {
    step_15: i64,
    occ_frac_1F_A: f32,
    occ_frac_1F_B: f32,
    occ_frac_1F_C: f32,
    occ_frac_1F_D: f32,
    occ_frac_2F_A: f32,
    occ_frac_2F_B: f32,
    hp_on_1F_A: f32,
    hp_on_1F_B: f32,
    hp_on_1F_C: f32,
    hp_on_1F_D: f32,
    hp_on_2F_A: f32,
    hp_on_2F_B: f32,
    preheat_lead_h: f32,
    stagger_min: f32,
    unocc_htg_sp_f: f32,
    occ_htg_sp_f: f32,
}

impl FixtureStep {
    fn into_control_step(self) -> ControlStep {
        ControlStep {
            occ: [
                self.occ_frac_1F_A,
                self.occ_frac_1F_B,
                self.occ_frac_1F_C,
                self.occ_frac_1F_D,
                self.occ_frac_2F_A,
                self.occ_frac_2F_B,
            ],
            hp: [
                self.hp_on_1F_A,
                self.hp_on_1F_B,
                self.hp_on_1F_C,
                self.hp_on_1F_D,
                self.hp_on_2F_A,
                self.hp_on_2F_B,
            ],
            preheat_lead_h: self.preheat_lead_h,
            stagger_min: self.stagger_min,
            unocc_htg_sp_f: self.unocc_htg_sp_f,
            occ_htg_sp_f: self.occ_htg_sp_f,
        }
    }
}

/// Resolve contracts directory: env override, then CARGO_MANIFEST_DIR sibling, then cwd.
pub fn contracts_dir() -> PathBuf {
    if let Some(p) = std::env::var_os("LAKESIDE_CONTRACTS_DIR") {
        return PathBuf::from(p);
    }
    let manifest_sibling = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("contracts")
        .join(CONTRACT_VERSION);
    if manifest_sibling.is_dir() {
        return manifest_sibling;
    }
    Path::new("contracts").join(CONTRACT_VERSION)
}

/// Load a desktop control strategy by id. Fail-closed if missing; reject PRBS.
pub fn load_control_schedule(strategy_id: &str) -> Result<ControlSchedule> {
    if strategy_id.starts_with("prbs") {
        bail!("PRBS not offered on desktop; use farm-only PRBS arms (strategy_id={strategy_id})");
    }
    let path = contracts_dir().join(format!("{strategy_id}.json"));
    if !path.is_file() {
        bail!(
            "missing control contract {} — run scripts/export_control_contracts.py",
            path.display()
        );
    }
    let txt = std::fs::read_to_string(&path)
        .with_context(|| format!("read {}", path.display()))?;
    let doc: FixtureDoc =
        serde_json::from_str(&txt).with_context(|| format!("parse {}", path.display()))?;
    if doc.contract_version != CONTRACT_VERSION {
        bail!(
            "control contract_version {} != expected {}",
            doc.contract_version,
            CONTRACT_VERSION
        );
    }
    if doc.strategy_id != strategy_id {
        bail!(
            "fixture strategy_id {} != requested {}",
            doc.strategy_id,
            strategy_id
        );
    }
    if doc.steps.len() != STEPS_96 {
        bail!(
            "control fixture {} has {} steps, expected {}",
            strategy_id,
            doc.steps.len(),
            STEPS_96
        );
    }
    for (i, s) in doc.steps.iter().enumerate() {
        if s.step_15 as usize != i {
            bail!(
                "control fixture {}: steps[{i}].step_15={} (expected {i})",
                strategy_id,
                s.step_15
            );
        }
    }
    // OCC_FRAC_COLS / HP_ON_COLS order must stay aligned with FixtureStep mapping.
    debug_assert_eq!(OCC_FRAC_COLS.len(), 6);
    debug_assert_eq!(HP_ON_COLS.len(), 6);

    let steps: Vec<ControlStep> = doc
        .steps
        .into_iter()
        .map(FixtureStep::into_control_step)
        .collect();
    Ok(ControlSchedule {
        strategy_id: doc.strategy_id,
        steps,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn load_baseline_96_overnight_zero() {
        let sched = load_control_schedule("baseline").expect("load baseline.json");
        assert_eq!(sched.strategy_id, "baseline");
        assert_eq!(sched.steps.len(), 96);
        let s0 = &sched.steps[0];
        for z in 0..6 {
            assert!(
                (s0.occ[z] - 0.0).abs() < 1e-6,
                "baseline step0 occ[{z}] should be 0"
            );
            assert!(
                (s0.hp[z] - 0.0).abs() < 1e-6,
                "baseline step0 hp[{z}] should be 0"
            );
        }
        assert!((s0.preheat_lead_h - 1.0).abs() < 1e-6);
        assert!((s0.stagger_min - 0.0).abs() < 1e-6);
        assert!((s0.unocc_htg_sp_f - 64.994).abs() < 1e-3);
        assert!((s0.occ_htg_sp_f - 68.0).abs() < 1e-6);
        // Occupancy begins at step 28 in baseline fixture.
        let s28 = &sched.steps[28];
        assert!((s28.occ[0] - 1.0).abs() < 1e-6);
        assert!((s28.hp[0] - 1.0).abs() < 1e-6);
    }

    #[test]
    fn reject_prbs() {
        let err = load_control_schedule("prbs_a").unwrap_err();
        let msg = format!("{err:#}");
        assert!(
            msg.to_lowercase().contains("prbs"),
            "expected PRBS rejection, got: {msg}"
        );
    }
}
