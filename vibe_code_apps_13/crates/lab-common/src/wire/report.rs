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

/// Write JSON via temp file + rename in the same directory.
///
/// # Errors
///
/// Returns I/O errors from create/write/rename.
pub fn atomic_write_json(path: &Path, report: &WireReport) -> io::Result<()> {
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
        let body = serde_json::to_vec_pretty(report)
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
