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
    atomic_write_json, resolve_same_device, FailureRecord, LatencyStats, ReportStatus, WireReport,
};
pub use timing::deadline_ms;
