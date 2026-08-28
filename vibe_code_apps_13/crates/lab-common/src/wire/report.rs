//! Atomic JSON hardware report helpers.

use std::fs;
use std::io::{self, Write};
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

use super::envelope::Direction;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ReportStatus {
    Passed,
    Failed,
    Interrupted,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WireReport {
    pub schema_version: String,
    pub status: ReportStatus,
    pub reason: String,
    pub started_utc: String,
    pub ended_utc: String,
    pub elapsed_ms: u64,
    pub port_a: String,
    pub port_b: String,
    pub port_a_resolved: String,
    pub port_b_resolved: String,
    pub baud: u32,
    pub rounds_requested: u32,
    pub rounds_completed: u32,
    pub seed: u64,
    pub max_payload: u16,
    pub timeout_ms: u64,
    pub turnaround_guard_ms: u64,
    pub envelopes_ok_a_to_b: u64,
    pub envelopes_ok_b_to_a: u64,
    pub payload_bytes_a_to_b: u64,
    pub payload_bytes_b_to_a: u64,
    pub local_echo_a: u64,
    pub local_echo_b: u64,
    pub missing: u64,
    pub corrupt: u64,
    pub duplicate: u64,
    pub stale: u64,
    pub unexpected: u64,
    pub parser_rejected: u64,
    pub serial_errors: u64,
    pub latency_ms_a_to_b: LatencyStats,
    pub latency_ms_b_to_a: LatencyStats,
    pub failures: Vec<FailureRecord>,
    pub os: String,
    pub arch: String,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct LatencyStats {
    pub samples: u64,
    pub min_ms: f64,
    pub mean_ms: f64,
    pub max_ms: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FailureRecord {
    pub round: u32,
    pub direction: String,
    pub sequence: u32,
    pub kind: String,
    pub detail: String,
}

impl LatencyStats {
    pub fn push(&mut self, ms: f64) {
        if self.samples == 0 {
            self.min_ms = ms;
            self.max_ms = ms;
            self.mean_ms = ms;
            self.samples = 1;
            return;
        }
        self.min_ms = self.min_ms.min(ms);
        self.max_ms = self.max_ms.max(ms);
        #[allow(clippy::cast_precision_loss)]
        let n = self.samples as f64;
        self.mean_ms = (self.mean_ms * n + ms) / (n + 1.0);
        self.samples += 1;
    }
}

impl WireReport {
    #[must_use]
    pub fn peer_ok(&self) -> bool {
        self.missing == 0
            && self.corrupt == 0
            && self.duplicate == 0
            && self.status == ReportStatus::Passed
    }
}

/// Live snapshot for Streamlit / dashboards during long hardware runs.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ProgressStatus {
    Running,
    Passed,
    Failed,
    Interrupted,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WireProgress {
    pub schema_version: String,
    pub status: ProgressStatus,
    pub updated_utc: String,
    pub report_path: String,
    pub rounds_requested: u32,
    pub rounds_completed: u32,
    pub elapsed_ms: u64,
    pub envelopes_ok_a_to_b: u64,
    pub envelopes_ok_b_to_a: u64,
    pub missing: u64,
    pub corrupt: u64,
    pub duplicate: u64,
    pub latency_mean_a_to_b_ms: f64,
    pub latency_mean_b_to_a_ms: f64,
    /// Last ~120 round-trip samples (ms) for a sparkline in the dashboard.
    pub recent_latency_ms: Vec<f64>,
}

impl WireProgress {
    #[must_use]
    pub fn from_report(report: &WireReport, status: ProgressStatus, report_path: &Path) -> Self {
        Self {
            schema_version: "phase1_wire_progress_v1".into(),
            status,
            updated_utc: chrono_lite_utc_now(),
            report_path: report_path.display().to_string(),
            rounds_requested: report.rounds_requested,
            rounds_completed: report.rounds_completed,
            elapsed_ms: report.elapsed_ms,
            envelopes_ok_a_to_b: report.envelopes_ok_a_to_b,
            envelopes_ok_b_to_a: report.envelopes_ok_b_to_a,
            missing: report.missing,
            corrupt: report.corrupt,
            duplicate: report.duplicate,
            latency_mean_a_to_b_ms: report.latency_ms_a_to_b.mean_ms,
            latency_mean_b_to_a_ms: report.latency_ms_b_to_a.mean_ms,
            recent_latency_ms: Vec::new(),
        }
    }

    pub fn push_recent_latency(&mut self, ms: f64) {
        const CAP: usize = 120;
        self.recent_latency_ms.push(ms);
        if self.recent_latency_ms.len() > CAP {
            let drop_n = self.recent_latency_ms.len() - CAP;
            self.recent_latency_ms.drain(..drop_n);
        }
    }
}

fn chrono_lite_utc_now() -> String {
    // Avoid pulling chrono into lab-common; RFC3339-ish from std is enough for dashboards.
    use std::time::{SystemTime, UNIX_EPOCH};
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or(0, |d| d.as_secs());
    format!("{secs}")
}

/// Default live progress path: `wire-test-38400.json` → `wire-test-38400-live.json`.
#[must_use]
pub fn default_progress_path(report: &Path) -> PathBuf {
    let stem = report
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("wire-test");
    report.with_file_name(format!("{stem}-live.json"))
}

/// Write JSON via temp file + rename in the same directory.
///
/// # Errors
///
/// Returns I/O errors from create/write/rename.
pub fn atomic_write_json(path: &Path, report: &WireReport) -> io::Result<()> {
    atomic_write_value(path, report)
}

/// Write a live progress snapshot (same atomic rename pattern as the final report).
///
/// # Errors
///
/// Returns I/O errors from create/write/rename.
pub fn atomic_write_progress(path: &Path, progress: &WireProgress) -> io::Result<()> {
    atomic_write_value(path, progress)
}

fn atomic_write_value<T: Serialize>(path: &Path, value: &T) -> io::Result<()> {
    if let Some(parent) = path.parent() {
        if !parent.as_os_str().is_empty() {
            fs::create_dir_all(parent)?;
        }
    }
    let tmp = {
        let mut t = PathBuf::from(path);
        let name = path
            .file_name()
            .and_then(|s| s.to_str())
            .unwrap_or("report.json");
        t.set_file_name(format!(".{name}.tmp"));
        t
    };
    {
        let mut f = fs::File::create(&tmp)?;
        let body = serde_json::to_vec_pretty(value)
            .map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))?;
        f.write_all(&body)?;
        f.write_all(b"\n")?;
        f.sync_all()?;
    }
    fs::rename(&tmp, path)?;
    Ok(())
}

/// Resolve both paths and reject identical devices.
///
/// # Errors
///
/// Returns an error string when paths are empty or resolve to the same device.
pub fn resolve_same_device(port_a: &Path, port_b: &Path) -> Result<(PathBuf, PathBuf), String> {
    if port_a.as_os_str().is_empty() || port_b.as_os_str().is_empty() {
        return Err("port paths must be nonempty".into());
    }
    let a = fs::canonicalize(port_a).unwrap_or_else(|_| port_a.to_path_buf());
    let b = fs::canonicalize(port_b).unwrap_or_else(|_| port_b.to_path_buf());
    if a == b {
        return Err(format!(
            "port-a and port-b resolve to the same device: {}",
            a.display()
        ));
    }
    Ok((a, b))
}

impl From<Direction> for String {
    fn from(value: Direction) -> Self {
        value.to_string()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn atomic_round_trip() {
        let stamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let path = std::env::temp_dir().join(format!("wire-report-{stamp}.json"));
        let report = WireReport {
            schema_version: "phase1_wire_v1".into(),
            status: ReportStatus::Passed,
            reason: "ok".into(),
            started_utc: "t0".into(),
            ended_utc: "t1".into(),
            elapsed_ms: 1,
            port_a: "a".into(),
            port_b: "b".into(),
            port_a_resolved: "a".into(),
            port_b_resolved: "b".into(),
            baud: 38400,
            rounds_requested: 1,
            rounds_completed: 1,
            seed: 1,
            max_payload: 256,
            timeout_ms: 1000,
            turnaround_guard_ms: 5,
            envelopes_ok_a_to_b: 1,
            envelopes_ok_b_to_a: 1,
            payload_bytes_a_to_b: 0,
            payload_bytes_b_to_a: 0,
            local_echo_a: 0,
            local_echo_b: 0,
            missing: 0,
            corrupt: 0,
            duplicate: 0,
            stale: 0,
            unexpected: 0,
            parser_rejected: 0,
            serial_errors: 0,
            latency_ms_a_to_b: LatencyStats::default(),
            latency_ms_b_to_a: LatencyStats::default(),
            failures: vec![],
            os: "test".into(),
            arch: "test".into(),
        };
        atomic_write_json(&path, &report).unwrap();
        let loaded: WireReport = serde_json::from_slice(&fs::read(&path).unwrap()).unwrap();
        assert_eq!(loaded.status, ReportStatus::Passed);
        let _ = fs::remove_file(&path);
    }

    #[test]
    fn rejects_same_resolved_path() {
        let err = resolve_same_device(Path::new("/tmp"), Path::new("/tmp")).unwrap_err();
        assert!(err.contains("same device"));
    }
}
