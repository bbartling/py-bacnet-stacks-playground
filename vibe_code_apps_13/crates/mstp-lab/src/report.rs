//! JSON acceptance report for mstp-probe.

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StepResult {
    pub step: String,
    pub ok: bool,
    pub detail: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub latency_ms: Option<f64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AcceptanceReport {
    pub mode: String,
    pub status: String,
    pub device_instance: u32,
    pub probe_mac: u8,
    pub device_mac: u8,
    pub baud: u32,
    pub steps: Vec<StepResult>,
    pub passed: u32,
    pub failed: u32,
}

impl AcceptanceReport {
    pub fn new(mode: &str, device_instance: u32, probe_mac: u8, device_mac: u8, baud: u32) -> Self {
        Self {
            mode: mode.to_owned(),
            status: "running".to_owned(),
            device_instance,
            probe_mac,
            device_mac,
            baud,
            steps: Vec::new(),
            passed: 0,
            failed: 0,
        }
    }

    pub fn push_step(
        &mut self,
        step: &str,
        ok: bool,
        detail: impl Into<String>,
        latency_ms: Option<f64>,
    ) {
        if ok {
            self.passed += 1;
        } else {
            self.failed += 1;
        }
        self.steps.push(StepResult {
            step: step.to_owned(),
            ok,
            detail: detail.into(),
            latency_ms,
        });
    }

    pub fn finalize(&mut self) {
        self.status = if self.failed == 0 { "Passed" } else { "Failed" }.to_owned();
    }
}
