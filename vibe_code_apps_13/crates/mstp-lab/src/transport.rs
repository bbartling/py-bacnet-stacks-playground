//! MS/TP transport helpers.

use anyhow::{Context, Result};
use bacnet_transport::mstp::{MstpConfig, MstpTransport};
use bacnet_transport::mstp_serial::{SerialConfig, TokioSerialPort};
use lab_common::{BaudRate, MstpMasterConfig};

pub struct MstpEndpoint {
    pub transport: MstpTransport<TokioSerialPort>,
    pub mac: u8,
}

pub fn mstp_config_from_lab(cfg: &MstpMasterConfig) -> MstpConfig {
    MstpConfig {
        this_station: cfg.mac,
        max_master: cfg.max_master,
        max_info_frames: cfg.max_info_frames,
        baud_rate: cfg.baud.as_u32(),
    }
}

/// Open serial + MS/TP transport from a fully validated [`MstpMasterConfig`].
///
/// Callers must set baud/mac/max_master/max_info_frames explicitly — this does
/// not substitute a default baud.
pub fn open_mstp_transport(cfg: &MstpMasterConfig) -> Result<MstpEndpoint> {
    cfg.validate().map_err(anyhow::Error::msg)?;
    let serial = TokioSerialPort::open(&SerialConfig {
        port_name: cfg.serial_path.clone(),
        baud_rate: cfg.baud.as_u32(),
    })
    .context("open serial port")?;
    let transport = MstpTransport::new(serial, mstp_config_from_lab(cfg));
    Ok(MstpEndpoint {
        mac: cfg.mac,
        transport,
    })
}

/// Build a master config with explicit baud (no silent 38400 substitution).
pub fn master_config(
    serial_path: &str,
    mac: u8,
    baud: BaudRate,
    max_master: u8,
    max_info_frames: u8,
) -> MstpMasterConfig {
    MstpMasterConfig {
        serial_path: serial_path.to_owned(),
        baud,
        mac,
        max_master,
        max_info_frames,
    }
}
