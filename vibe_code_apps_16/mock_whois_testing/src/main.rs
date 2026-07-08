//! mock_scan — isolate the open-fdd Who-Is discovery vs local-server socket conflict.
//!
//! Hypothesis (VOLTTRON proxy-agent style): a local BACnet server that owns
//! UDP :47808 and a discovery client on an *ephemeral* port cannot both run —
//! broadcast I-Am replies are addressed to :47808 and land on the server socket,
//! so the ephemeral client never sees them and discovery returns nothing.
//!
//! open-fdd `client_bind_port()` returns 0 (ephemeral) whenever the local 599999
//! server is enabled (always on the bench). This reproduces that exact shape.
//!
//! Scenarios:
//!   --bind-port 47808                     WORKING pattern (whois-scan): client owns :47808
//!   --bind-port 0                         ephemeral client, no server (isolate port effect)
//!   --with-local-server --bind-port 0     OPEN-FDD REPRO: server owns :47808, client ephemeral
//!
//! Prints the discovered device set for each so an A/B/C comparison is trivial.

use std::net::Ipv4Addr;
use std::process;
use std::sync::Arc;
use std::time::Duration;

use anyhow::{Context, Result};
use bacnet_client::client::BACnetClient;
use bacnet_objects::analog::AnalogInputObject;
use bacnet_objects::database::ObjectDatabase;
use bacnet_objects::device::{DeviceConfig, DeviceObject};
use bacnet_server::server::BACnetServer;
use bacnet_types::enums::ObjectType;
use bacnet_types::primitives::ObjectIdentifier;
use clap::Parser;
use tokio::sync::Mutex;
use tracing::{info, warn};

#[derive(Parser, Debug)]
#[command(name = "mock_scan", about = "Reproduce open-fdd Who-Is vs local-server socket conflict")]
struct Args {
    /// UDP port for the discovery client (0 = ephemeral, 47808 = well-known)
    #[arg(long, default_value_t = 47808)]
    bind_port: u16,

    /// Spawn a local BACnet server on :47808 BEFORE scanning (open-fdd 599999 pattern)
    #[arg(long)]
    with_local_server: bool,

    /// Local server device instance
    #[arg(long, default_value_t = 599999)]
    server_instance: u32,

    /// Local NIC IPv4 (auto-detects enp3s0 if omitted)
    #[arg(long, short = 'i')]
    interface: Option<Ipv4Addr>,

    /// Subnet directed broadcast (default /24 from interface)
    #[arg(long, short = 'b')]
    broadcast: Option<Ipv4Addr>,

    /// Device instance range low
    #[arg(long, default_value_t = 0)]
    low: u32,

    /// Device instance range high
    #[arg(long, default_value_t = 4_194_303)]
    high: u32,

    /// Also send a routed who_is_network to this MSTP network (e.g. 2000 for device 5007)
    #[arg(long)]
    router_net: Option<u16>,

    /// Seconds to wait for I-Am after Who-Is
    #[arg(long, short = 't', default_value_t = 6)]
    timeout: u64,

    /// Human label for the scenario (printed in the summary)
    #[arg(long, default_value = "scan")]
    label: String,
}

fn detect_enp3s0_address() -> Option<Ipv4Addr> {
    let output = process::Command::new("ip")
        .args(["-4", "addr", "show", "dev", "enp3s0"])
        .output()
        .ok()?;
    for line in String::from_utf8_lossy(&output.stdout).lines() {
        if let Some(rest) = line.trim().strip_prefix("inet ") {
            if let Some(ip) = rest.split_whitespace().next() {
                if let Some(base) = ip.split('/').next() {
                    if let Ok(ip) = base.parse::<Ipv4Addr>() {
                        return Some(ip);
                    }
                }
            }
        }
    }
    None
}

fn subnet_broadcast(ip: Ipv4Addr) -> Ipv4Addr {
    let o = ip.octets();
    Ipv4Addr::new(o[0], o[1], o[2], 255)
}

fn build_server_db(instance: u32) -> Result<ObjectDatabase> {
    let mut db = ObjectDatabase::new();
    let mut ai = AnalogInputObject::new(1, "mock-local-ai", 62)?;
    ai.set_present_value(72.5);
    db.add(Box::new(ai))?;

    let device_oid = ObjectIdentifier::new(ObjectType::DEVICE, instance)?;
    let mut object_list = vec![device_oid];
    let mut points = db.list_objects();
    points.sort_by_key(|o| (o.object_type().to_raw(), o.instance_number()));
    object_list.extend(points);

    let mut device = DeviceObject::new(DeviceConfig {
        instance,
        name: "MockLocalServer".into(),
        vendor_name: "mock-whois-testing".into(),
        vendor_id: 999,
        model_name: "mock-local-server".into(),
        max_apdu_length: 1476,
        ..DeviceConfig::default()
    })?;
    device.set_object_list(object_list);
    db.add(Box::new(device))?;
    Ok(db)
}

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter("info,bacnet_transport=warn,bacnet_server=warn,bacnet_client=warn")
        .init();

    let args = Args::parse();
    let iface = args
        .interface
        .or_else(detect_enp3s0_address)
        .unwrap_or(Ipv4Addr::UNSPECIFIED);
    let bcast = args.broadcast.unwrap_or_else(|| {
        if iface.is_unspecified() {
            Ipv4Addr::BROADCAST
        } else {
            subnet_broadcast(iface)
        }
    });

    info!("=== scenario: {} ===", args.label);
    info!(
        "iface={iface} broadcast={bcast} client_bind_port={} with_local_server={} range={}..{}",
        args.bind_port, args.with_local_server, args.low, args.high
    );

    // Optionally stand up a local server that OWNS :47808 (open-fdd 599999 pattern).
    let _server = if args.with_local_server {
        let db = build_server_db(args.server_instance)?;
        let server = BACnetServer::bip_builder()
            .interface(Ipv4Addr::UNSPECIFIED)
            .port(47808)
            .broadcast_address(bcast)
            .vendor_id(999)
            .database(db)
            .build()
            .await
            .context("local server failed to bind :47808 (is another BACnet process holding it?)")?;
        let mac = server.local_mac().to_vec();
        info!(
            "local server {} up on :47808 MAC={:02x?} (owns the well-known port)",
            args.server_instance, mac
        );
        Some(Arc::new(Mutex::new(server)))
    } else {
        None
    };

    // Discovery client — port per scenario.
    let mut client = BACnetClient::bip_builder()
        .interface(iface)
        .port(args.bind_port)
        .broadcast_address(bcast)
        .apdu_timeout_ms(6000)
        .build()
        .await
        .context("discovery client build failed")?;

    info!("sending Who-Is {}..{}", args.low, args.high);
    client
        .who_is(Some(args.low), Some(args.high))
        .await
        .map_err(|e| anyhow::anyhow!("who_is: {e}"))?;

    if let Some(net) = args.router_net {
        info!("sending routed who_is_network dnet={net}");
        let _ = client
            .who_is_network(net, Some(args.low), Some(args.high))
            .await;
    }

    tokio::time::sleep(Duration::from_secs(args.timeout)).await;

    let devices = client.discovered_devices().await;
    let _ = client.stop().await;

    println!("\n================ RESULT [{}] ================", args.label);
    println!(
        "client_bind_port={} with_local_server={} -> discovered {} device(s)",
        args.bind_port,
        args.with_local_server,
        devices.len()
    );
    let mut instances: Vec<u32> = devices
        .iter()
        .map(|d| d.object_identifier.instance_number())
        .collect();
    instances.sort_unstable();
    for d in &devices {
        println!(
            "  device {:>7}  addr {:<21}  net={:?}",
            d.object_identifier.instance_number(),
            {
                let m = d.mac_address.as_slice();
                if m.len() == 6 {
                    format!(
                        "{}.{}.{}.{}:{}",
                        m[0],
                        m[1],
                        m[2],
                        m[3],
                        u16::from_be_bytes([m[4], m[5]])
                    )
                } else {
                    format!("{m:02x?}")
                }
            },
            d.source_network
        );
    }
    println!("  instances: {instances:?}");
    println!("=============================================\n");

    if devices.is_empty() {
        warn!(
            "NO devices discovered in scenario '{}' — if this is the ephemeral+server case, that is the conflict.",
            args.label
        );
    }
    Ok(())
}
