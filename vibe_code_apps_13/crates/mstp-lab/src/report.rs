//! JSON acceptance report for mstp-probe.

use serde::{Deserialize, Serialize};

/// Acceptance intensity: smoke is CI-safe; gate requires full step set + ≥500 reads.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AcceptanceProfile {
    Smoke,
    Gate,
}

impl AcceptanceProfile {
    #[must_use]
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Smoke => "smoke",
            Self::Gate => "gate",
        }
    }
}

impl std::str::FromStr for AcceptanceProfile {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.trim().to_ascii_lowercase().as_str() {
            "smoke" => Ok(Self::Smoke),
            "gate" => Ok(Self::Gate),
            other => Err(format!(
                "unknown profile '{other}'; expected 'smoke' or 'gate'"
            )),
        }
    }
}

/// Required step names for a gate Passed result (order-independent membership).
pub const GATE_REQUIRED_STEPS: &[&str] = &[
    "start_client_server",
    "token_stabilize",
    "who_is_iam",
    "read_device_object_name",
    "read_device_object_list",
    "read_ai_present_value",
    "read_bi_present_value",
    "read_property_multiple",
    "write_av_priority_8",
    "read_av_after_write",
    "relinquish_av_priority_8",
    "read_av_after_relinquish",
    "write_bv_priority_8",
    "read_bv_after_write",
    "relinquish_bv_priority_8",
    "read_bv_after_relinquish",
    "unknown_object_error",
    "write_ai_denied",
    "repeated_reads",
    "shutdown",
];

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StepResult {
    pub step: String,
    pub ok: bool,
    pub detail: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub latency_ms: Option<f64>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct LatencySummary {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub min_ms: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mean_ms: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub p50_ms: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub p95_ms: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub p99_ms: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_ms: Option<f64>,
    pub samples: u32,
}

impl LatencySummary {
    #[must_use]
    pub fn from_samples(mut samples: Vec<f64>) -> Self {
        let n = samples.len();
        if n == 0 {
            return Self::default();
        }
        samples.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
        let min = samples[0];
        let max = samples[n - 1];
        let mean = samples.iter().sum::<f64>() / n as f64;
        let pct = |p: f64| {
            let idx = ((p * (n as f64 - 1.0)).round() as usize).min(n - 1);
            samples[idx]
        };
        Self {
            min_ms: Some(min),
            mean_ms: Some(mean),
            p50_ms: Some(pct(0.50)),
            p95_ms: Some(pct(0.95)),
            p99_ms: Some(pct(0.99)),
            max_ms: Some(max),
            samples: u32::try_from(n).unwrap_or(u32::MAX),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AcceptanceReport {
    pub schema_version: String,
    pub profile: String,
    pub mode: String,
    pub status: String,
    pub started_utc: String,
    pub ended_utc: String,
    pub baud: u32,
    pub probe_mac: u8,
    pub device_mac: u8,
    pub max_master: u8,
    pub max_info_frames: u8,
    pub device_instance: u32,
    pub vendor_id: u16,
    pub rusty_bacnet_commit: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub project_git_commit: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub probe_serial: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub device_serial: Option<String>,
    /// True only when a real USB MS/TP hardware run produced this report.
    pub hardware_evidence: bool,
    pub steps: Vec<StepResult>,
    pub latency: LatencySummary,
    pub passed: u32,
    pub failed: u32,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub shutdown_ok: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub shutdown_detail: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub kernel: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub arch: Option<String>,
}

impl AcceptanceReport {
    pub const SCHEMA_VERSION: &'static str = "phase2_acceptance_v2";
    pub const RUSTY_BACNET_COMMIT: &'static str = "e3b9edbd5d96d25e21855d5b1ca02f8e070bb1ef";

    #[must_use]
    pub fn new(
        profile: AcceptanceProfile,
        mode: &str,
        device_instance: u32,
        probe_mac: u8,
        device_mac: u8,
        baud: u32,
        max_master: u8,
        max_info_frames: u8,
        vendor_id: u16,
        hardware_evidence: bool,
    ) -> Self {
        Self {
            schema_version: Self::SCHEMA_VERSION.to_owned(),
            profile: profile.as_str().to_owned(),
            mode: mode.to_owned(),
            status: "running".to_owned(),
            started_utc: chrono_now(),
            ended_utc: String::new(),
            baud,
            probe_mac,
            device_mac,
            max_master,
            max_info_frames,
            device_instance,
            vendor_id,
            rusty_bacnet_commit: Self::RUSTY_BACNET_COMMIT.to_owned(),
            project_git_commit: project_git_commit(),
            probe_serial: None,
            device_serial: None,
            hardware_evidence,
            steps: Vec::new(),
            latency: LatencySummary::default(),
            passed: 0,
            failed: 0,
            shutdown_ok: None,
            shutdown_detail: None,
            kernel: None,
            arch: Some(std::env::consts::ARCH.to_owned()),
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

    /// Gate Passed requires every required step present and ok; smoke only needs zero failures.
    pub fn finalize(&mut self, profile: AcceptanceProfile) {
        self.ended_utc = chrono_now();
        if profile == AcceptanceProfile::Gate {
            let gate_ok = GATE_REQUIRED_STEPS
                .iter()
                .all(|required| self.steps.iter().any(|s| s.step == *required && s.ok));
            if !gate_ok {
                self.push_step(
                    "gate_completeness",
                    false,
                    "missing or failed required gate step(s)",
                    None,
                );
            }
        }
        self.status = if self.failed == 0 { "Passed" } else { "Failed" }.to_owned();
    }
}

fn chrono_now() -> String {
    // Avoid chrono dep: RFC3339-ish via system time if available; else empty.
    use std::time::{SystemTime, UNIX_EPOCH};
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    format!("{secs}")
}

fn project_git_commit() -> Option<String> {
    std::process::Command::new("git")
        .args(["rev-parse", "HEAD"])
        .output()
        .ok()
        .filter(|o| o.status.success())
        .and_then(|o| String::from_utf8(o.stdout).ok())
        .map(|s| s.trim().to_owned())
        .filter(|s| !s.is_empty())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn gate_fails_when_any_required_step_missing() {
        for missing in GATE_REQUIRED_STEPS {
            let mut report = AcceptanceReport::new(
                AcceptanceProfile::Gate,
                "loopback",
                123_001,
                0,
                1,
                38_400,
                10,
                1,
                999,
                false,
            );
            for step in GATE_REQUIRED_STEPS {
                if step == missing {
                    continue;
                }
                report.push_step(step, true, "ok", None);
            }
            report.finalize(AcceptanceProfile::Gate);
            assert_eq!(
                report.status, "Failed",
                "gate must fail when missing step {missing}"
            );
        }
    }

    #[test]
    fn gate_passes_when_all_required_present() {
        let mut report = AcceptanceReport::new(
            AcceptanceProfile::Gate,
            "loopback",
            123_001,
            0,
            1,
            38_400,
            10,
            1,
            999,
            false,
        );
        for step in GATE_REQUIRED_STEPS {
            report.push_step(step, true, "ok", None);
        }
        report.finalize(AcceptanceProfile::Gate);
        assert_eq!(report.status, "Passed");
        assert!(!report.hardware_evidence);
    }
}
