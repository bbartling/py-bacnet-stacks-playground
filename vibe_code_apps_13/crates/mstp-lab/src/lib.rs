//! Shared MS/TP lab helpers: mini-device object model, transport wiring, acceptance runner.

#![allow(clippy::similar_names, clippy::too_many_lines, clippy::cast_precision_loss, clippy::missing_errors_doc, clippy::must_use_candidate, clippy::assigning_clones)]

mod acceptance;
mod database;
mod report;
mod transport;

pub use acceptance::{run_hardware_acceptance, run_loopback_acceptance, AcceptanceOptions};
pub use database::{build_mini_device_database, MiniDeviceConfig, MSTP_MAX_APDU, UNITS_DEGF, VENDOR_ID};
pub use report::{AcceptanceReport, StepResult};
pub use transport::{mstp_config_from_lab, open_mstp_transport, MstpEndpoint};
