//! Open-FDD BACnet server mimic — library.
//!
//! A small BACnet/IP **server** (device 599999) plus a **probe** client for bench tests.
//!
//! ```text
//! src/
//!   lib.rs       — crate root (this file)
//!   config.rs    — CLI defaults (device id, port, vendor)
//!   network.rs   — IP / broadcast / UDP bind helpers
//!   database.rs  — BACnet object list (AV/BV points from Open-FDD)
//!   server.rs    — run the BACnet server
//!   probe.rs     — unicast read + Who-Is test client
//!   bin/
//!     server.rs  — `openfdd-bacnet-mimic` entry point
//!     probe.rs   — `bacnet-probe` entry point
//! ```

pub mod config;
pub mod database;
pub mod network;
pub mod probe;
pub mod server;

pub use config::{ProbeArgs, ServerArgs, DEFAULT_DEVICE_ID, DEFAULT_DEVICE_NAME, OPENFDD_VENDOR_ID};
