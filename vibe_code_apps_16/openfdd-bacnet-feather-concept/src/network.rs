//! NIC / broadcast helpers (same patterns as openfdd-bacnet-mimic).

use std::net::{Ipv4Addr, SocketAddrV4};
use std::process::Command;
use std::time::Duration;

use socket2::{Domain, Protocol, Socket, Type};
use tracing::info;

#[derive(Clone, Copy, Debug)]
pub struct NetworkConfig {
    pub device_ip: Ipv4Addr,
    pub bind_ip: Ipv4Addr,
    pub broadcast: Ipv4Addr,
}

pub fn resolve_network(
    address: Option<Ipv4Addr>,
    broadcast: Option<Ipv4Addr>,
    nic: &str,
) -> NetworkConfig {
    let device_ip = address
        .or_else(|| detect_ipv4_on_nic(nic))
        .unwrap_or(Ipv4Addr::UNSPECIFIED);

    if address.is_none() {
        if let Some(ip) = detect_ipv4_on_nic(nic) {
            info!("auto-detected {nic}: {ip}");
        }
    }

    let broadcast = broadcast.unwrap_or_else(|| {
        if device_ip.is_unspecified() {
            Ipv4Addr::BROADCAST
        } else {
            subnet_broadcast(device_ip)
        }
    });

    NetworkConfig {
        device_ip,
        bind_ip: Ipv4Addr::UNSPECIFIED,
        broadcast,
    }
}

pub fn detect_ipv4_on_nic(nic: &str) -> Option<Ipv4Addr> {
    let output = Command::new("ip")
        .args(["-4", "addr", "show", "dev", nic])
        .output()
        .ok()?;

    for line in String::from_utf8_lossy(&output.stdout).lines() {
        let rest = line.trim().strip_prefix("inet ")?;
        let ip_str = rest.split_whitespace().next()?;
        let base = ip_str.split('/').next()?;
        if let Ok(ip) = base.parse::<Ipv4Addr>() {
            return Some(ip);
        }
    }
    None
}

pub fn subnet_broadcast(ip: Ipv4Addr) -> Ipv4Addr {
    let o = ip.octets();
    Ipv4Addr::new(o[0], o[1], o[2], 255)
}

pub fn verify_udp_bind(bind_ip: Ipv4Addr, port: u16) -> anyhow::Result<()> {
    let socket = Socket::new(Domain::IPV4, Type::DGRAM, Some(Protocol::UDP))?;
    socket.set_reuse_address(true)?;
    socket.bind(&SocketAddrV4::new(bind_ip, port).into())?;
    info!("UDP bind OK on {bind_ip}:{port}");
    Ok(())
}

pub fn free_udp_port(port: u16) {
    let spec = format!("{port}/udp");
    let _ = Command::new("fuser").args(["-k", &spec]).output();
    std::thread::sleep(Duration::from_millis(500));
}

/// BACnet virtual MAC for rusty-bacnet BIP: `<host-ip>:BA:C0` (port encoded in last two bytes for default).
pub fn server_mac_from_host_ip(ip: Ipv4Addr) -> Vec<u8> {
    let o = ip.octets();
    vec![o[0], o[1], o[2], o[3], 0xBA, 0xC0]
}

/// BIP MAC for a host listening on a non-default BACnet port.
/// rusty-bacnet encodes port in the last two bytes when not 0xBAC0.
pub fn server_mac_from_host_port(ip: Ipv4Addr, port: u16) -> Vec<u8> {
    let o = ip.octets();
    if port == 0xBAC0 {
        return server_mac_from_host_ip(ip);
    }
    let p = port.to_be_bytes();
    vec![o[0], o[1], o[2], o[3], p[0], p[1]]
}
