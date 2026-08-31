//! Shared MS/TP lab helpers: mini-device object model, transport wiring, acceptance runner.

#![allow(
    clippy::similar_names,
    clippy::too_many_lines,
    clippy::cast_precision_loss,
    clippy::cast_possible_truncation,
    clippy::cast_sign_loss,
    clippy::missing_errors_doc,
    clippy::must_use_candidate,
    clippy::assigning_clones,
    clippy::doc_markdown,
    clippy::too_many_arguments,
    clippy::map_unwrap_or,
    clippy::cast_lossless
)]

mod acceptance;
mod database;
mod report;
mod token_edges;
mod transport;

pub use acceptance::{run_hardware_acceptance, run_loopback_acceptance, AcceptanceOptions};
pub use database::{
    apply_simulated_inputs, build_mini_device_database, network_write_ai_denied, MiniDeviceConfig,
    LAB_VENDOR_ID, MSTP_MAX_APDU, UNITS_DEGF,
};
pub use report::{
    AcceptanceProfile, AcceptanceReport, LatencySummary, StepResult, GATE_REQUIRED_STEPS,
};
pub use token_edges::{TokenEdge, TokenEdgeCounters};
pub use transport::{master_config, mstp_config_from_lab, open_mstp_transport, MstpEndpoint};

/// Pinned `jscott3201/rusty-bacnet` git revision (must match workspace `Cargo.toml`).
pub const RUSTY_BACNET_REV: &str = env!("RUSTY_BACNET_REV");
