//! CLI flags and default values (device 599999, port 47808, bench NIC).

use std::net::Ipv4Addr;

use bacnet_transport::bip::DEFAULT_BACNET_PORT;
use clap::Parser;

/// Open-FDD vendor id (used in Device object + server builder).
pub const OPENFDD_VENDOR_ID: u16 = 999;

/// Default BACnet device instance (matches Open-FDD edge).
pub const DEFAULT_DEVICE_ID: u32 = 599999;

/// Default BACnet device name.
pub const DEFAULT_DEVICE_NAME: &str = "OpenFDD";

/// Default NIC name on the field bench (override with `OPENFDD_BACNET_NIC`).
pub const DEFAULT_NIC: &str = "enp3s0";

#[derive(Parser, Debug)]
#[command(
    name = "openfdd-bacnet-mimic",
    about = "Open-FDD BACnet/IP server — answers Who-Is, no periodic I-Am"
)]
pub struct ServerArgs {
    /// Device object name
    #[arg(long, default_value = DEFAULT_DEVICE_NAME)]
    pub name: String,

    /// BACnet device instance number
    #[arg(long, default_value_t = DEFAULT_DEVICE_ID)]
    pub instance: u32,

    /// Host IPv4 advertised in I-Am (auto-detected from NIC if omitted)
    #[arg(long)]
    pub address: Option<Ipv4Addr>,

    /// UDP port (BACnet/IP default 47808 = 0xBAC0)
    #[arg(long, default_value_t = DEFAULT_BACNET_PORT)]
    pub port: u16,

    /// Subnet directed broadcast (defaults to x.x.x.255 from --address)
    #[arg(long)]
    pub broadcast: Option<Ipv4Addr>,

    /// Verbose rusty-bacnet logs
    #[arg(long)]
    pub debug: bool,

    /// Kill any process already bound to the BACnet port before starting
    #[arg(long)]
    pub replace_existing: bool,
}

#[derive(Parser, Debug)]
#[command(
    name = "bacnet-probe",
    about = "Test client: unicast read + global Who-Is against a running server"
)]
pub struct ProbeArgs {
    /// Client bind address (same subnet as the server)
    #[arg(long)]
    pub bind: Option<Ipv4Addr>,

    /// Directed broadcast address
    #[arg(long)]
    pub broadcast: Option<Ipv4Addr>,

    /// Expected device instance in Who-Is results
    #[arg(long, default_value_t = DEFAULT_DEVICE_ID)]
    pub device: u32,
}
