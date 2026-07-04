//! Open-FDD concept: BACnet mini-device + poller + atomic Feather store.
//!
//! Binaries:
//! - `bacnet_app` — server + updater + poller/writer (terminal 1)
//! - `feather_tail` — reads completed `.feather` files (terminal 2)

pub mod app_config;
pub mod feather_store;
pub mod latest;
pub mod mini_device;
pub mod network;
pub mod poller;
