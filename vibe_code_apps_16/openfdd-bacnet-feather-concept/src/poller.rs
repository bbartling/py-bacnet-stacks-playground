//! Field poller — reads device 5007 without binding :47808.
//!
//! Mini-device alone owns UDP 47808 (Workbench object-list).
//! Field device 5007 is behind BIP router 192.168.204.200 on MSTP net 2000 MAC 7.
//! Plain `add_device` + BIP read returns **unknown-object**; must use **routed** ReadProperty
//! (same path Who-Is populates in rpm-read / point-discover samples).

use std::net::Ipv4Addr;
use std::time::Duration;

use anyhow::{Context, Result};
use bacnet_client::client::BACnetClient;
use bacnet_encoding::primitives::decode_application_value;
use bacnet_transport::bip::{BipTransport, DEFAULT_BACNET_PORT};
use bacnet_transport::bvll::encode_bip_mac;
use bacnet_types::enums::{ObjectType, PropertyIdentifier};
use bacnet_types::primitives::{ObjectIdentifier, PropertyValue};
use chrono::Utc;
use tracing::{info, warn};

use crate::app_config::{AppConfig, PollPointConfig};
use crate::feather_store::{write_samples_atomic, SampleRow};
use crate::latest::{LatestHandle, LatestReading};
use crate::network::{resolve_poller_bind, subnet_broadcast};

const DEFAULT_FIELD_HOST: Ipv4Addr = Ipv4Addr::new(192, 168, 204, 200);

fn is_local_mini_device(point: &PollPointConfig, cfg: &AppConfig) -> bool {
    point.device_instance == cfg.server.instance && point.host.is_none()
}

pub async fn run_poller_forever(cfg: AppConfig, latest: LatestHandle) -> Result<()> {
    let store = cfg.feather_store_folder();
    std::fs::create_dir_all(&store)
        .with_context(|| format!("creating store {}", store.display()))?;

    let nic = cfg.server.nic.clone();
    let bind = resolve_poller_bind(cfg.poller.bind, cfg.server.address, &nic);
    let broadcast = cfg
        .poller
        .broadcast
        .or(cfg.server.broadcast)
        .unwrap_or_else(|| subnet_broadcast(bind));

    info!(
        "poller bind={bind}:0 (ephemeral) broadcast={broadcast} interval={}s",
        cfg.poller.interval_secs
    );

    let client = BACnetClient::bip_builder()
        .interface(bind)
        .port(0)
        .broadcast_address(broadcast)
        .apdu_timeout_ms(8000)
        .build()
        .await
        .context("BACnetClient::build")?;

    for point in cfg.poller.points.iter().filter(|p| p.enabled) {
        if is_local_mini_device(point, &cfg) {
            continue;
        }
        let host = point.host.unwrap_or(DEFAULT_FIELD_HOST);
        let port = point.port.unwrap_or(DEFAULT_BACNET_PORT);
        let mstp = cfg.poller.mstp_network;
        let mac = point.mstp_mac.as_deref().unwrap_or(&[7]);
        info!(
            "field point {} → router {host}:{port} net={mstp} mstp_mac={mac:?} (routed ReadProperty)",
            point.point_name
        );
    }

    let interval = Duration::from_secs(cfg.poller.interval_secs.max(1));

    loop {
        let mut rows = Vec::new();
        for point in cfg.poller.points.iter().filter(|p| p.enabled) {
            match read_one_point(&client, point, &cfg).await {
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
                    if !is_local_mini_device(point, &cfg) {
                        *latest.write().await = Some(LatestReading {
                            present_value: row.present_value,
                        });
                    }
                    rows.push(row);
                }
                Err(err) => {
                    warn!(
                        "read failed {} device={} {}:{} — {err:#}",
                        point.point_name,
                        point.device_instance,
                        point.object_type,
                        point.object_instance
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
    client: &BACnetClient<BipTransport>,
    point: &PollPointConfig,
    cfg: &AppConfig,
) -> Result<SampleRow> {
    let object_type = parse_object_type(&point.object_type)?;
    let oid = ObjectIdentifier::new(object_type, point.object_instance)?;

    let value = if is_local_mini_device(point, cfg) {
        let host = cfg
            .server
            .address
            .unwrap_or(Ipv4Addr::new(192, 168, 204, 55));
        let mac = encode_bip_mac(host.octets(), cfg.server.port);
        let ack = client
            .read_property(&mac, oid, PropertyIdentifier::PRESENT_VALUE, None)
            .await
            .context("ReadProperty local clone")?;
        decode_real(&ack.property_value)?
    } else {
        // Routed read: BIP router + MSTP MAC (Workbench Netwk / MAC Addr columns).
        let host = point.host.unwrap_or(DEFAULT_FIELD_HOST);
        let port = point.port.unwrap_or(DEFAULT_BACNET_PORT);
        let router_mac = encode_bip_mac(host.octets(), port);
        let mstp_net = cfg.poller.mstp_network;
        let mstp_mac = point.mstp_mac.clone().unwrap_or_else(|| vec![7]);

        let ack = client
            .read_property_routed(
                &router_mac,
                mstp_net,
                &mstp_mac,
                oid,
                PropertyIdentifier::PRESENT_VALUE,
                None,
            )
            .await
            .with_context(|| {
                format!(
                    "ReadProperty routed device {} via {host}:{port} net={mstp_net} mac={mstp_mac:?}",
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

fn parse_object_type(s: &str) -> Result<ObjectType> {
    match s.to_ascii_lowercase().replace('-', "_").as_str() {
        "analog_input" | "ai" => Ok(ObjectType::ANALOG_INPUT),
        "analog_value" | "av" => Ok(ObjectType::ANALOG_VALUE),
        "analog_output" | "ao" => Ok(ObjectType::ANALOG_OUTPUT),
        other => anyhow::bail!("unsupported object_type '{other}'"),
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
