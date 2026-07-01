//! Shared library for the Open-FDD BACnet mimic.
//!
//! Both apps import from here. Start reading the **programs** instead:
//!
//! - **Server:** `src/server/main.rs` → `./scripts/run.sh`
//! - **Client:**  `src/client/main.rs` → `./scripts/probe.sh`

pub mod shared;

pub use shared::config::{
    ProbeArgs, ServerArgs, DEFAULT_DEVICE_ID, DEFAULT_DEVICE_NAME, OPENFDD_VENDOR_ID,
};
