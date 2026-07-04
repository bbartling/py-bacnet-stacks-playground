//! NIC / broadcast helpers (same patterns as openfdd-bacnet-mimic).

use std::net::{Ipv4Addr, SocketAddrV4};
use std::process::Command;
use std::time::Duration;

use socket2::{Domain, Protocol, Socket, Type};
use tracing::{info, warn};

#[derive(Clone, Copy, Debug)]
pub struct NetworkConfig {
    /// IP advertised in I-Am / used for BIP MAC (must be the OT LAN address).
    pub device_ip: Ipv4Addr,
    /// Socket bind (0.0.0.0 = all interfaces).
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
        .or_else(detect_first_lan_ipv4)
        .unwrap_or(Ipv4Addr::UNSPECIFIED);

    if device_ip.is_unspecified() {
        warn!(
            "could not detect OT LAN IP on nic={nic} — set server.address / poller.bind in config"
        );
    } else if address.is_none() {
        info!("using OT LAN IP {device_ip} (nic={nic})");
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

/// Prefer explicit bind, else OT LAN IP (never fall back to 127.0.0.1 for field polling).
pub fn resolve_poller_bind(
    bind: Option<Ipv4Addr>,
    server_address: Option<Ipv4Addr>,
    nic: &str,
) -> Ipv4Addr {
    if let Some(ip) = bind {
        return ip;
    }
    if let Some(ip) = server_address {
        return ip;
    }
    if let Some(ip) = detect_ipv4_on_nic(nic) {
        return ip;
    }
    if let Some(ip) = detect_first_lan_ipv4() {
        return ip;
    }
    warn!("poller bind fell back to 127.0.0.1 — field Who-Is will fail; set poller.bind");
    Ipv4Addr::LOCALHOST
}

pub fn detect_ipv4_on_nic(nic: &str) -> Option<Ipv4Addr> {
    for ip_bin in ["ip", "/usr/sbin/ip", "/sbin/ip", "/usr/bin/ip"] {
        let output = Command::new(ip_bin)
            .args(["-4", "-o", "addr", "show", "dev", nic])
            .output()
            .ok()?;
        if !output.status.success() {
            continue;
        }
        // Example: `2: enp3s0    inet 192.168.204.55/24 brd 192.168.204.255 ...`
        let text = String::from_utf8_lossy(&output.stdout);
        for part in text.split_whitespace() {
            if let Some(addr) = part.split('/').next() {
                if let Ok(ip) = addr.parse::<Ipv4Addr>() {
                    if !ip.is_loopback() {
                        return Some(ip);
                    }
                }
            }
        }
    }
    None
}

/// First non-loopback, non-docker IPv4 on the host.
pub fn detect_first_lan_ipv4() -> Option<Ipv4Addr> {
    for ip_bin in ["ip", "/usr/sbin/ip", "/sbin/ip", "/usr/bin/ip"] {
        let output = Command::new(ip_bin)
            .args(["-4", "-o", "addr", "show", "up"])
            .output()
            .ok()?;
        if !output.status.success() {
            continue;
        }
        for line in String::from_utf8_lossy(&output.stdout).lines() {
            if line.contains("docker") || line.contains("br-") || line.contains(" veth") {
                continue;
            }
            for part in line.split_whitespace() {
                if let Some(addr) = part.split('/').next() {
                    if let Ok(ip) = addr.parse::<Ipv4Addr>() {
                        if !ip.is_loopback() && !ip.is_link_local() && !ip.is_unspecified() {
                            // Skip typical docker bridges
                            let o = ip.octets();
                            if o[0] == 172 && (o[1] == 17 || o[1] == 18) {
                                continue;
                            }
                            return Some(ip);
                        }
                    }
                }
            }
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

/// BACnet virtual MAC for rusty-bacnet BIP: `<host-ip>:BA:C0`.
pub fn server_mac_from_host_ip(ip: Ipv4Addr) -> Vec<u8> {
    let o = ip.octets();
    vec![o[0], o[1], o[2], o[3], 0xBA, 0xC0]
}

/// BIP MAC for a host listening on a non-default BACnet port.
pub fn server_mac_from_host_port(ip: Ipv4Addr, port: u16) -> Vec<u8> {
    let o = ip.octets();
    if port == 0xBAC0 {
        return server_mac_from_host_ip(ip);
    }
    let p = port.to_be_bytes();
    vec![o[0], o[1], o[2], o[3], p[0], p[1]]
}
