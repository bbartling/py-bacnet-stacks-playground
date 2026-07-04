//! Shared app state (poller → mini-device clone AV + APP-FAULT BI).

use std::sync::Arc;
use std::time::Instant;

use tokio::sync::RwLock;

/// Live state mirrored onto the mini-device.
#[derive(Debug, Clone)]
pub struct AppState {
    /// Latest successful DUCT-T reading (°F) for AV clone.
    pub duct_t: Option<f64>,
    /// `true` = FAULT (active on BI); `false` = healthy (inactive).
    pub fault: bool,
    /// When the last fully-successful field poll finished.
    pub last_ok_at: Option<Instant>,
    /// Short reason for the current fault (logging / description).
    pub fault_reason: String,
}

impl Default for AppState {
    fn default() -> Self {
        Self {
            duct_t: None,
            // Start in fault until the first successful poll cycle.
            fault: true,
            last_ok_at: None,
            fault_reason: "waiting for first field poll".into(),
        }
    }
}

pub type AppStateHandle = Arc<RwLock<AppState>>;

pub fn new_app_state() -> AppStateHandle {
    Arc::new(RwLock::new(AppState::default()))
}
