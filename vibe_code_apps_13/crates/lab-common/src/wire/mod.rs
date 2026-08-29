//! Private Phase 1 wire envelope — not `BACnet` / MS/TP.

mod envelope;
mod parser;
mod report;
mod timing;

pub use envelope::{
    encode_envelope, Direction, Envelope, EnvelopeError, PayloadPattern, BOUNDARY_LENGTHS,
    PREAMBLE, PROTOCOL_VERSION,
};
pub use parser::{EnvelopeParser, ParseEvent};
pub use report::{
    atomic_write_json, atomic_write_progress, atomic_write_serde, default_progress_path,
    resolve_same_device, FailureRecord, LatencyStats, ProgressStatus, ReportStatus, WireProgress,
    WireReport,
};
pub use timing::deadline_ms;
