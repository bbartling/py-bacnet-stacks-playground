//! Runtime config from TOML (mini-device + multi-device poller).

use std::net::Ipv4Addr;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result};
use serde::Deserialize;

/// Open-FDD-style vendor id for the concept mini-device.
pub const VENDOR_ID: u16 = 999;

/// Degrees Fahrenheit engineering units (BACnet).
/// BACnet engineering units: degrees-Fahrenheit = 64 (62 is Celsius — Workbench shows °C if wrong).
pub const TEMP_UNITS_DEGREES_F: u32 = 64;
/// Percent relative humidity (BACnet engineering units).
pub const UNITS_PERCENT_RH: u32 = 29;
/// Miles per hour (BACnet engineering units).
pub const UNITS_MILES_PER_HOUR: u32 = 72;

#[derive(Debug, Clone, Deserialize)]
pub struct AppConfig {
    #[serde(default)]
    pub store: StoreConfig,
    #[serde(default)]
    pub server: ServerConfig,
    #[serde(default)]
    pub poller: PollerConfig,
    #[serde(default)]
    pub weather: WeatherConfig,
}

#[derive(Debug, Clone, Deserialize)]
pub struct StoreConfig {
    #[serde(default = "default_store_dir")]
    pub dir: PathBuf,
    #[serde(default = "default_store_file")]
    pub file: String,
}

fn default_store_dir() -> PathBuf {
    PathBuf::from("data/feather_store")
}

fn default_store_file() -> String {
    "telemetry.feather".into()
}

impl Default for StoreConfig {
    fn default() -> Self {
        Self {
            dir: default_store_dir(),
            file: default_store_file(),
        }
    }
}

#[derive(Debug, Clone, Deserialize)]
pub struct ServerConfig {
    #[serde(default = "default_true")]
    pub enabled: bool,
    #[serde(default = "default_device_instance")]
    pub instance: u32,
    #[serde(default = "default_device_name")]
    pub name: String,
    #[serde(default = "default_server_port")]
    pub port: u16,
    #[serde(default = "default_nic")]
    pub nic: String,
    pub address: Option<Ipv4Addr>,
    pub broadcast: Option<Ipv4Addr>,
    #[serde(default = "default_server_update_secs")]
    pub value_update_secs: u64,
    #[serde(default = "default_ai_instance")]
    pub temp_object_instance: u32,
    #[serde(default = "default_temp_name")]
    pub temp_point_name: String,
    /// Field `point_name` that feeds the clone AV (must match a poller point).
    #[serde(default = "default_clone_from")]
    pub clone_from_point: String,
    #[serde(default = "default_status_instance")]
    pub status_object_instance: u32,
    #[serde(default = "default_status_name")]
    pub status_point_name: String,
}

fn default_true() -> bool {
    true
}
fn default_device_instance() -> u32 {
    5000
}
fn default_device_name() -> String {
    "openfdd-bacnet-feather-concept".into()
}
fn default_server_port() -> u16 {
    47808
}
fn default_nic() -> String {
    std::env::var("OPENFDD_BACNET_NIC").unwrap_or_else(|_| "enp3s0".into())
}
fn default_server_update_secs() -> u64 {
    2
}
fn default_ai_instance() -> u32 {
    1
}
fn default_temp_name() -> String {
    "5007-duct-t-clone".into()
}
fn default_clone_from() -> String {
    "DUCT-T".into()
}
fn default_status_instance() -> u32 {
    1
}
fn default_status_name() -> String {
    "APP-FAULT".into()
}

impl Default for ServerConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            instance: default_device_instance(),
            name: default_device_name(),
            port: default_server_port(),
            nic: default_nic(),
            address: None,
            broadcast: None,
            value_update_secs: default_server_update_secs(),
            temp_object_instance: default_ai_instance(),
            temp_point_name: default_temp_name(),
            clone_from_point: default_clone_from(),
            status_object_instance: default_status_instance(),
            status_point_name: default_status_name(),
        }
    }
}

/// VOLTTRON-inspired multi-device poller.
///
/// Each device has its own scrape interval + phase offset. The scheduler wakes
/// on `tick_ms`, picks overdue devices (most overdue first), and scrapes at most
/// `max_concurrent` devices at a time — same idea as platform.driver spreading
/// load across many drivers instead of one giant synchronous loop.
#[derive(Debug, Clone, Deserialize)]
pub struct PollerConfig {
    /// Scheduler wake interval (ms).
    #[serde(default = "default_tick_ms")]
    pub tick_ms: u64,
    /// Max devices scraping in parallel.
    #[serde(default = "default_max_concurrent")]
    pub max_concurrent: usize,
    /// Default scrape interval when a device omits `interval_secs`.
    #[serde(default = "default_poll_interval")]
    pub interval_secs: u64,
    pub bind: Option<Ipv4Addr>,
    pub broadcast: Option<Ipv4Addr>,
    #[serde(default)]
    pub devices: Vec<DeviceConfig>,
}

fn default_tick_ms() -> u64 {
    250
}
fn default_max_concurrent() -> usize {
    2
}
fn default_poll_interval() -> u64 {
    10
}

/// One BACnet device (driver) — analogous to a VOLTTRON platform.driver config.
#[derive(Debug, Clone, Deserialize)]
pub struct DeviceConfig {
    pub name: String,
    #[serde(default = "default_true")]
    pub enabled: bool,
    pub device_instance: u32,
    pub host: Ipv4Addr,
    #[serde(default = "default_bacnet_port")]
    pub port: u16,
    /// When set with `mstp_mac`, uses routed ReadProperty (MSTP behind BIP router).
    pub mstp_network: Option<u16>,
    pub mstp_mac: Option<Vec<u8>>,
    /// Per-device scrape interval (VOLTTRON driver interval).
    pub interval_secs: Option<u64>,
    /// Phase offset so devices don't all scrape on the same second.
    #[serde(default)]
    pub offset_secs: u64,
    /// When true, failures raise APP-FAULT (clone source device).
    #[serde(default)]
    pub critical: bool,
    #[serde(default)]
    pub points: Vec<DevicePointConfig>,
}

fn default_bacnet_port() -> u16 {
    47808
}

#[derive(Debug, Clone, Deserialize)]
pub struct DevicePointConfig {
    #[serde(default = "default_true")]
    pub enabled: bool,
    #[serde(default = "default_object_type")]
    pub object_type: String,
    pub object_instance: u32,
    pub point_name: String,
    #[serde(default = "default_units")]
    pub units: String,
}

fn default_object_type() -> String {
    "analog-input".into()
}
fn default_units() -> String {
    "".into()
}

impl DeviceConfig {
    pub fn interval_or(&self, default_secs: u64) -> u64 {
        self.interval_secs.unwrap_or(default_secs).max(1)
    }

    pub fn is_routed(&self) -> bool {
        self.mstp_mac.is_some()
    }
}

impl Default for PollerConfig {
    fn default() -> Self {
        Self {
            tick_ms: default_tick_ms(),
            max_concurrent: default_max_concurrent(),
            interval_secs: default_poll_interval(),
            bind: None,
            broadcast: None,
            devices: default_devices(),
        }
    }
}

fn default_devices() -> Vec<DeviceConfig> {
    vec![bens_bench_device(), bens_fake_ahu_device()]
}

fn bens_bench_device() -> DeviceConfig {
    let ai = |inst: u32, name: &str, units: &str| DevicePointConfig {
        enabled: true,
        object_type: "analog-input".into(),
        object_instance: inst,
        point_name: name.into(),
        units: units.into(),
    };
    DeviceConfig {
        name: "BENS-BENCH".into(),
        enabled: true,
        device_instance: 5007,
        host: Ipv4Addr::new(192, 168, 204, 200),
        port: 47808,
        mstp_network: Some(2000),
        mstp_mac: Some(vec![7]),
        interval_secs: Some(10),
        offset_secs: 0,
        critical: true,
        points: vec![
            ai(1168, "OA-H", "%RH"),
            ai(1173, "OA-T", "°F"),
            ai(1192, "DUCT-T", "°F"),
            ai(9334, "DUCT-P", "in/wc"),
            ai(10014, "STAT ZN-T", "°F"),
            ai(10044, "ACTUATOR-POS", "%"),
            DevicePointConfig {
                enabled: true,
                object_type: "analog-output".into(),
                object_instance: 2466,
                point_name: "ACTUATOR-0".into(),
                units: "%".into(),
            },
        ],
    }
}

fn bens_fake_ahu_device() -> DeviceConfig {
    let ai = |inst: u32, name: &str, units: &str| DevicePointConfig {
        enabled: true,
        object_type: "analog-input".into(),
        object_instance: inst,
        point_name: name.into(),
        units: units.into(),
    };
    let ao = |inst: u32, name: &str, units: &str| DevicePointConfig {
        enabled: true,
        object_type: "analog-output".into(),
        object_instance: inst,
        point_name: name.into(),
        units: units.into(),
    };
    let av = |inst: u32, name: &str, units: &str| DevicePointConfig {
        enabled: true,
        object_type: "analog-value".into(),
        object_instance: inst,
        point_name: name.into(),
        units: units.into(),
    };
    DeviceConfig {
        name: "BensFakeAhu".into(),
        enabled: true,
        device_instance: 3456789,
        host: Ipv4Addr::new(192, 168, 204, 13),
        port: 47808,
        mstp_network: None,
        mstp_mac: None,
        interval_secs: Some(10),
        // Stagger 5s after BENS-BENCH (VOLTTRON-style phase offset).
        offset_secs: 5,
        critical: false,
        points: vec![
            ai(1, "DAP-P", "in/wc"),
            ai(2, "SA-T", "°F"),
            ai(3, "MA-T", "°F"),
            ai(4, "RA-T", "°F"),
            ai(5, "SA-FLOW", "cfm"),
            ai(6, "OA-T", "°F"),
            ai(7, "ELEC-PWR", "kW"),
            ao(1, "SF-O", "%"),
            ao(2, "HTG-O", "%"),
            ao(3, "CLG-O", "%"),
            ao(4, "DPR-O", "%"),
            av(1, "DAP-SP", "in/wc"),
            av(2, "SAT-SP", "°F"),
            av(3, "OAT-NETWORK", "°F"),
            DevicePointConfig {
                enabled: true,
                object_type: "binary-input".into(),
                object_instance: 1,
                point_name: "SF-S".into(),
                units: "bool".into(),
            },
            DevicePointConfig {
                enabled: true,
                object_type: "binary-output".into(),
                object_instance: 1,
                point_name: "SF-C".into(),
                units: "bool".into(),
            },
            DevicePointConfig {
                enabled: true,
                object_type: "multi-state-value".into(),
                object_instance: 1,
                point_name: "Occ-Schedule".into(),
                units: "state".into(),
            },
        ],
    }
}

impl AppConfig {
    pub fn load() -> Result<Self> {
        if let Ok(path) = std::env::var("OPENFDD_FEATHER_CONCEPT_CONFIG") {
            return Self::load_from(Path::new(&path));
        }
        for candidate in ["config/config.toml", "config/default.toml"] {
            let path = Path::new(candidate);
            if path.is_file() {
                return Self::load_from(path);
            }
        }
        tracing::warn!("no config/config.toml found — using built-in defaults");
        Ok(Self::default())
    }

    pub fn load_from(path: &Path) -> Result<Self> {
        if !path.is_file() {
            tracing::warn!(
                "config {} not found — using built-in defaults",
                path.display()
            );
            return Ok(Self::default());
        }
        let text = std::fs::read_to_string(path)
            .with_context(|| format!("reading config {}", path.display()))?;
        let cfg: Self = toml::from_str(&text)
            .with_context(|| format!("parsing config {}", path.display()))?;
        Ok(cfg)
    }

    pub fn feather_store_folder(&self) -> PathBuf {
        self.store.dir.clone()
    }

    pub fn feather_store_path(&self) -> PathBuf {
        self.store.dir.join(&self.store.file)
    }
}

/// Open-Meteo outdoor weather → BACnet AVs (polled on a slow interval).
#[derive(Debug, Clone, Deserialize)]
pub struct WeatherConfig {
    #[serde(default = "default_true")]
    pub enabled: bool,
    /// City for geocoding (default Madison Wisconsin).
    #[serde(default = "default_weather_city")]
    pub city: String,
    /// How often to call Open-Meteo (default 20 minutes).
    #[serde(default = "default_weather_interval")]
    pub interval_secs: u64,
    #[serde(default = "default_fallback_temp")]
    pub fallback_temp_f: f64,
    #[serde(default = "default_fallback_humidity")]
    pub fallback_humidity: f64,
    #[serde(default = "default_fallback_wind")]
    pub fallback_wind_mph: f64,
    #[serde(default = "default_wx_temp_inst")]
    pub temp_object_instance: u32,
    #[serde(default = "default_wx_rh_inst")]
    pub humidity_object_instance: u32,
    #[serde(default = "default_wx_wind_inst")]
    pub wind_object_instance: u32,
    #[serde(default = "default_wx_dp_inst")]
    pub dewpoint_object_instance: u32,
    #[serde(default = "default_wx_temp_name")]
    pub temp_point_name: String,
    #[serde(default = "default_wx_rh_name")]
    pub humidity_point_name: String,
    #[serde(default = "default_wx_wind_name")]
    pub wind_point_name: String,
    #[serde(default = "default_wx_dp_name")]
    pub dewpoint_point_name: String,
}

fn default_weather_city() -> String {
    "Madison Wisconsin".into()
}
fn default_weather_interval() -> u64 {
    1200
}
fn default_fallback_temp() -> f64 {
    70.0
}
fn default_fallback_humidity() -> f64 {
    50.0
}
fn default_fallback_wind() -> f64 {
    0.0
}
fn default_wx_temp_inst() -> u32 {
    2
}
fn default_wx_rh_inst() -> u32 {
    3
}
fn default_wx_wind_inst() -> u32 {
    4
}
fn default_wx_dp_inst() -> u32 {
    5
}
fn default_wx_temp_name() -> String {
    "OA-WEATHER-T".into()
}
fn default_wx_rh_name() -> String {
    "OA-WEATHER-RH".into()
}
fn default_wx_wind_name() -> String {
    "OA-WEATHER-WIND".into()
}
fn default_wx_dp_name() -> String {
    "OA-WEATHER-DP".into()
}

impl Default for WeatherConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            city: default_weather_city(),
            interval_secs: default_weather_interval(),
            fallback_temp_f: default_fallback_temp(),
            fallback_humidity: default_fallback_humidity(),
            fallback_wind_mph: default_fallback_wind(),
            temp_object_instance: default_wx_temp_inst(),
            humidity_object_instance: default_wx_rh_inst(),
            wind_object_instance: default_wx_wind_inst(),
            dewpoint_object_instance: default_wx_dp_inst(),
            temp_point_name: default_wx_temp_name(),
            humidity_point_name: default_wx_rh_name(),
            wind_point_name: default_wx_wind_name(),
            dewpoint_point_name: default_wx_dp_name(),
        }
    }
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            store: StoreConfig::default(),
            server: ServerConfig::default(),
            poller: PollerConfig::default(),
            weather: WeatherConfig::default(),
        }
    }
}

pub fn feather_store_folder() -> PathBuf {
    AppConfig::load()
        .map(|c| c.feather_store_folder())
        .unwrap_or_else(|_| default_store_dir())
}
