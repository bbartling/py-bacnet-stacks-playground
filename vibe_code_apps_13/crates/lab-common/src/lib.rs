//! Shared validation and Phase 1 wire-test primitives for checkpoint 13.

mod baud;
mod wire;

pub use baud::{validate_router_networks, BaudRate, ConfigError, MstpMasterConfig};
pub use wire::{
    atomic_write_json, deadline_ms, encode_envelope, resolve_same_device, Direction, Envelope,
    EnvelopeError, EnvelopeParser, FailureRecord, LatencyStats, ParseEvent, PayloadPattern,
    ReportStatus, WireReport, BOUNDARY_LENGTHS, PREAMBLE, PROTOCOL_VERSION,
};
