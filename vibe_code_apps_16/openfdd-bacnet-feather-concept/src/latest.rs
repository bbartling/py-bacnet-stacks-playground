//! Shared latest field reading (poller → mini-device AV clone).

use std::sync::Arc;

use tokio::sync::RwLock;

/// Latest successful poll of the field sensor (e.g. device 5007 AI:1192).
#[derive(Debug, Clone, Copy)]
pub struct LatestReading {
    pub present_value: f64,
}

pub type LatestHandle = Arc<RwLock<Option<LatestReading>>>;

pub fn new_latest() -> LatestHandle {
    Arc::new(RwLock::new(None))
}
