//! BACnet client probe: unicast read + global Who-Is.

use std::time::Duration;

use bacnet_client::client::BACnetClient;
use bacnet_encoding::primitives::decode_application_value;
use bacnet_types::enums::{ObjectType, PropertyIdentifier};
use bacnet_types::primitives::ObjectIdentifier;

use crate::config::ProbeArgs;
use crate::network::{detect_ipv4_on_nic, nic_from_env, server_mac_from_host_ip, subnet_broadcast};

#[derive(Debug)]
pub struct ProbeResult {
    pub unicast_ok: bool,
    pub unicast_detail: String,
    pub whois_count: usize,
    pub found_device: bool,
}

impl ProbeResult {
    pub fn whois_ok(&self) -> bool {
        self.found_device
    }
}

pub async fn run(args: ProbeArgs) -> Result<ProbeResult, Box<dyn std::error::Error>> {
    let nic = nic_from_env();
    let bind = args
        .bind
        .or_else(|| detect_ipv4_on_nic(&nic))
        .ok_or("set --bind or configure OPENFDD_BACNET_NIC with an IPv4 address")?;
    let broadcast = args.broadcast.unwrap_or_else(|| subnet_broadcast(bind));

    let server_mac = server_mac_from_host_ip(bind);
    let mut client = BACnetClient::bip_builder()
        .interface(bind)
        .port(0)
        .broadcast_address(broadcast)
        .build()
        .await?;

    let device_oid = ObjectIdentifier::new(ObjectType::DEVICE, args.device)?;
    let (unicast_ok, unicast_detail) = match client
        .read_property(&server_mac, device_oid, PropertyIdentifier::OBJECT_NAME, None)
        .await
    {
        Ok(ack) => {
            if let Ok((val, _)) = decode_application_value(&ack.property_value, 0) {
                (true, format!("object-name = {val:?}"))
            } else {
                (true, "read OK".into())
            }
        }
        Err(e) => (false, e.to_string()),
    };

    client.who_is(None, None).await?;
    tokio::time::sleep(Duration::from_secs(2)).await;

    let devices = client.discovered_devices().await;
    let found = devices
        .iter()
        .any(|d| d.object_identifier.instance_number() == args.device);

    if unicast_ok {
        println!("PASS  unicast read — {unicast_detail}");
    } else {
        println!("FAIL  unicast read — {unicast_detail}");
    }

    println!("Who-Is from {bind} broadcast={broadcast} expect device {}", args.device);
    for d in &devices {
        println!(
            "  device {} mac={:?}",
            d.object_identifier.instance_number(),
            d.mac_address
        );
    }
    println!(
        "discovered_total={} found_{}={found}",
        devices.len(),
        args.device
    );

    if !found {
        eprintln!(
            "NOTE: same-host Who-Is often returns 0 (rusty-bacnet ignores I-Am from same IP:47808)."
        );
        eprintln!("      Tridium / another PC on the LAN is the real discover test.");
    }

    let _ = client.stop().await;

    Ok(ProbeResult {
        unicast_ok,
        unicast_detail,
        whois_count: devices.len(),
        found_device: found,
    })
}
