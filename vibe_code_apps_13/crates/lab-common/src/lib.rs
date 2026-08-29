//! Shared validation and Phase 1 wire-test primitives for checkpoint 13.

mod baud;
mod wire;

pub use baud::{validate_router_networks, BaudRate, ConfigError, MstpMasterConfig};
pub use wire::{
    atomic_write_json, atomic_write_progress, atomic_write_serde, deadline_ms,
    default_progress_path, encode_envelope, resolve_same_device, Direction, Envelope,
    EnvelopeError, EnvelopeParser, FailureRecord, LatencyStats, ParseEvent, PayloadPattern,
    ProgressStatus, ReportStatus, WireProgress, WireReport, BOUNDARY_LENGTHS, PREAMBLE,
    PROTOCOL_VERSION,
};
