//! BACnet poller: ReadProperty on configured points, write Feather shards.

use std::net::Ipv4Addr;
use std::time::Duration;

use anyhow::{Context, Result};
use bacnet_client::client::BACnetClient;
use bacnet_encoding::primitives::decode_application_value;
use bacnet_transport::bip::BipTransport;
use bacnet_types::enums::{ObjectType, PropertyIdentifier};
use bacnet_types::primitives::{ObjectIdentifier, PropertyValue};
use chrono::Utc;
use tracing::{info, warn};

use crate::app_config::{AppConfig, PollPointConfig};
use crate::feather_store::{write_samples_atomic, SampleRow};
use crate::network::{
    detect_ipv4_on_nic, resolve_network, server_mac_from_host_port, subnet_broadcast,
};

pub async fn run_poller_forever(cfg: AppConfig) -> Result<()> {
    let store = cfg.feather_store_folder();
    std::fs::create_dir_all(&store)
        .with_context(|| format!("creating store {}", store.display()))?;

    let nic = cfg.server.nic.clone();
    let bind = cfg
        .poller
        .bind
        .or_else(|| detect_ipv4_on_nic(&nic))
        .unwrap_or(Ipv4Addr::LOCALHOST);
    let broadcast = cfg
        .poller
        .broadcast
        .unwrap_or_else(|| subnet_broadcast(bind));

    info!(
        "poller bind={bind} broadcast={broadcast} interval={}s store={}",
        cfg.poller.interval_secs,
        store.display()
    );

    let mut client = BACnetClient::bip_builder()
        .interface(bind)
        .port(0)
        .broadcast_address(broadcast)
        .build()
        .await
        .context("BACnetClient::build")?;

    // Discover field devices once (for optional device 5007 entries).
    if cfg
        .poller
        .points
        .iter()
        .any(|p| p.enabled && p.host.is_some())
    {
        info!("Who-Is for field points…");
        if let Err(err) = client.who_is(None, None).await {
            warn!("Who-Is failed: {err}");
        } else {
            tokio::time::sleep(Duration::from_secs(3)).await;
            let devices = client.discovered_devices().await;
            info!("Who-Is discovered {} device(s)", devices.len());
            for d in &devices {
                info!(
                    "  device {} mac={:?}",
                    d.object_identifier.instance_number(),
                    d.mac_address
                );
            }
        }
    }

    let interval = Duration::from_secs(cfg.poller.interval_secs.max(1));
    let local_net = resolve_network(cfg.server.address, cfg.server.broadcast, &cfg.server.nic);

    loop {
        let mut rows = Vec::new();
        for point in cfg.poller.points.iter().filter(|p| p.enabled) {
            match read_one_point(&mut client, point, &cfg, local_net.device_ip).await {
                Ok(row) => {
                    info!(
                        "polled {} device={} {}:{} = {:.2} {}",
                        row.point_name,
                        row.device_instance,
                        row.object_type,
                        row.object_instance,
                        row.present_value,
                        row.units
                    );
                    rows.push(row);
                }
                Err(err) => {
                    warn!(
                        "read failed device={} {}:{} — {err:#}",
                        point.device_instance, point.object_type, point.object_instance
                    );
                }
            }
        }

        if !rows.is_empty() {
            match write_samples_atomic(&store, &rows) {
                Ok(path) => info!("wrote feather {}", path.display()),
                Err(err) => warn!("feather write failed: {err:#}"),
            }
        }

        tokio::time::sleep(interval).await;
    }
}

async fn read_one_point(
    client: &mut BACnetClient<BipTransport>,
    point: &PollPointConfig,
    cfg: &AppConfig,
    local_device_ip: Ipv4Addr,
) -> Result<SampleRow> {
    let object_type = parse_object_type(&point.object_type)?;
    let oid = ObjectIdentifier::new(object_type, point.object_instance)?;

    let value = if let Some(host) = point.host {
        // Field device (e.g. 5007): prefer discovered MAC, else BIP MAC from host:port.
        let port = point.port.unwrap_or(47808);
        let mac = mac_for_device(client, point.device_instance, host, port).await;
        let ack = client
            .read_property(&mac, oid, PropertyIdentifier::PRESENT_VALUE, None)
            .await
            .with_context(|| format!("ReadProperty device {} @ {host}:{port}", point.device_instance))?;
        decode_real(&ack.property_value)?
    } else {
        // Local mini-device in this process.
        let host = if local_device_ip.is_unspecified() {
            Ipv4Addr::LOCALHOST
        } else {
            local_device_ip
        };
        let port = point.port.unwrap_or(cfg.server.port);
        let mac = server_mac_from_host_port(host, port);
        let ack = client
            .read_property(&mac, oid, PropertyIdentifier::PRESENT_VALUE, None)
            .await
            .with_context(|| {
                format!(
                    "ReadProperty local mini-device {} @ {host}:{port}",
                    point.device_instance
                )
            })?;
        decode_real(&ack.property_value)?
    };

    Ok(SampleRow {
        ts_utc: Utc::now(),
        device_instance: point.device_instance,
        object_type: point.object_type.to_ascii_lowercase(),
        object_instance: point.object_instance,
        point_name: point.point_name.clone(),
        present_value: value,
        units: point.units.clone(),
    })
}

async fn mac_for_device(
    client: &BACnetClient<BipTransport>,
    device_instance: u32,
    host: Ipv4Addr,
    port: u16,
) -> Vec<u8> {
    let devices = client.discovered_devices().await;
    if let Some(d) = devices
        .iter()
        .find(|d| d.object_identifier.instance_number() == device_instance)
    {
        return d.mac_address.to_vec();
    }
    server_mac_from_host_port(host, port)
}

fn parse_object_type(s: &str) -> Result<ObjectType> {
    match s.to_ascii_lowercase().as_str() {
        "analog-input" | "analog_input" | "ai" => Ok(ObjectType::ANALOG_INPUT),
        "analog-value" | "analog_value" | "av" => Ok(ObjectType::ANALOG_VALUE),
        other => anyhow::bail!("unsupported object_type '{other}' (use analog-input or analog-value)"),
    }
}

fn decode_real(bytes: &[u8]) -> Result<f64> {
    let (val, _) = decode_application_value(bytes, 0).context("decode_application_value")?;
    match val {
        PropertyValue::Real(v) => Ok(v as f64),
        PropertyValue::Double(v) => Ok(v),
        PropertyValue::Unsigned(v) => Ok(v as f64),
        PropertyValue::Signed(v) => Ok(v as f64),
        other => anyhow::bail!("unexpected property value {other:?}"),
    }
}
