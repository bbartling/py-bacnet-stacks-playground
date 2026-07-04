//! Runtime config from TOML (ports, mini-device, optional field device 5007).

use std::net::Ipv4Addr;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result};
use serde::Deserialize;

/// Open-FDD-style vendor id for the concept mini-device.
pub const VENDOR_ID: u16 = 999;

/// Degrees Fahrenheit engineering units (BACnet).
pub const TEMP_UNITS_DEGREES_F: u32 = 62;

#[derive(Debug, Clone, Deserialize)]
pub struct AppConfig {
    #[serde(default)]
    pub store: StoreConfig,
    #[serde(default)]
    pub server: ServerConfig,
    #[serde(default)]
    pub poller: PollerConfig,
}

#[derive(Debug, Clone, Deserialize)]
pub struct StoreConfig {
    /// Folder for atomic `.feather` shards (relative to CWD or absolute).
    #[serde(default = "default_store_dir")]
    pub dir: PathBuf,
}

fn default_store_dir() -> PathBuf {
    PathBuf::from("data/feather_store")
}

impl Default for StoreConfig {
    fn default() -> Self {
        Self {
            dir: default_store_dir(),
        }
    }
}

#[derive(Debug, Clone, Deserialize)]
pub struct ServerConfig {
    /// Start the local BACnet/IP mini-device in-process.
    #[serde(default = "default_true")]
    pub enabled: bool,
    #[serde(default = "default_device_instance")]
    pub instance: u32,
    #[serde(default = "default_device_name")]
    pub name: String,
    /// UDP port for the mini-device (use **47809** so OT/Open-FDD can keep **47808**).
    #[serde(default = "default_server_port")]
    pub port: u16,
    /// NIC for auto IP (e.g. `enp3s0`). Override with env `OPENFDD_BACNET_NIC`.
    #[serde(default = "default_nic")]
    pub nic: String,
    /// Advertised IPv4 in I-Am (auto-detect from NIC if omitted).
    pub address: Option<Ipv4Addr>,
    pub broadcast: Option<Ipv4Addr>,
    /// How often the mini-device updates AI:1 present-value.
    #[serde(default = "default_server_update_secs")]
    pub value_update_secs: u64,
    /// Local analog-input instance for the demo temp point.
    #[serde(default = "default_ai_instance")]
    pub temp_object_instance: u32,
    #[serde(default = "default_temp_name")]
    pub temp_point_name: String,
}

fn default_true() -> bool {
    true
}
fn default_device_instance() -> u32 {
    599998
}
fn default_device_name() -> String {
    "OpenFDD-Feather-Concept".into()
}
fn default_server_port() -> u16 {
    47809
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
    "demo-temp".into()
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
        }
    }
}

#[derive(Debug, Clone, Deserialize)]
pub struct PollerConfig {
    #[serde(default = "default_poll_interval")]
    pub interval_secs: u64,
    /// Client bind IP (auto from NIC if omitted).
    pub bind: Option<Ipv4Addr>,
    pub broadcast: Option<Ipv4Addr>,
    #[serde(default)]
    pub points: Vec<PollPointConfig>,
}

fn default_poll_interval() -> u64 {
    10
}

impl Default for PollerConfig {
    fn default() -> Self {
        Self {
            interval_secs: default_poll_interval(),
            bind: None,
            broadcast: None,
            points: vec![PollPointConfig {
                enabled: true,
                device_instance: default_device_instance(),
                object_type: "analog-input".into(),
                object_instance: default_ai_instance(),
                point_name: default_temp_name(),
                units: "°F".into(),
                // Empty host = read local mini-device on server.port via host MAC.
                host: None,
                port: None,
            }],
        }
    }
}

#[derive(Debug, Clone, Deserialize)]
pub struct PollPointConfig {
    #[serde(default = "default_true")]
    pub enabled: bool,
    pub device_instance: u32,
    /// `analog-input` or `analog-value` (case-insensitive).
    #[serde(default = "default_object_type")]
    pub object_type: String,
    pub object_instance: u32,
    pub point_name: String,
    #[serde(default = "default_units")]
    pub units: String,
    /// Optional unicast host IP (field device). If omitted, uses local mini-device MAC.
    pub host: Option<Ipv4Addr>,
    /// Optional BACnet/IP UDP port for the target (default: server.port for local, 47808 for field).
    pub port: Option<u16>,
}

fn default_object_type() -> String {
    "analog-input".into()
}
fn default_units() -> String {
    "°F".into()
}

impl AppConfig {
    /// Load TOML from `OPENFDD_FEATHER_CONCEPT_CONFIG` or `config/default.toml`.
    pub fn load() -> Result<Self> {
        let path = std::env::var("OPENFDD_FEATHER_CONCEPT_CONFIG")
            .map(PathBuf::from)
            .unwrap_or_else(|_| PathBuf::from("config/default.toml"));
        Self::load_from(&path)
    }

    pub fn load_from(path: &Path) -> Result<Self> {
        if !path.is_file() {
            tracing::warn!(
                "config {} not found — using built-in defaults (local mini-device :47809)",
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
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            store: StoreConfig::default(),
            server: ServerConfig::default(),
            poller: PollerConfig::default(),
        }
    }
}

/// Convenience for binaries that only need the store path.
pub fn feather_store_folder() -> PathBuf {
    AppConfig::load()
        .map(|c| c.feather_store_folder())
        .unwrap_or_else(|_| default_store_dir())
}
