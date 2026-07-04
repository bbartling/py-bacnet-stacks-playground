//! Shared app state (poller / weather → mini-device points).

use std::sync::Arc;
use std::time::Instant;

use tokio::sync::RwLock;

/// Outdoor weather mirrored onto OA-WEATHER-* AVs.
#[derive(Debug, Clone)]
pub struct WeatherReading {
    pub temp_f: f64,
    pub humidity: f64,
    pub wind_mph: f64,
    pub dewpoint_f: f64,
    /// `true` when values came from Open-Meteo; `false` for configured fallbacks.
    pub from_api: bool,
    pub location: String,
    pub reason: String,
    pub fetched_at: Instant,
}

/// Live state mirrored onto the mini-device.
#[derive(Debug, Clone)]
pub struct AppState {
    /// Latest successful DUCT-T reading (°F) for AV clone.
    pub duct_t: Option<f64>,
    /// Outdoor weather (API or fallback).
    pub weather: Option<WeatherReading>,
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
            weather: None,
            // Start in fault until the first healthy poll cycle.
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
