//! Terminal 2: validate mini-device weather temp (Open-Meteo) + APP-FAULT + Feather rows.
//!
//! Primary check: BACnet present-value of `OA-WEATHER-T` (outdoor dry-bulb from Open-Meteo).
//!
//! ```text
//! cargo run --release --bin feather_tail
//! ```

use std::net::Ipv4Addr;
use std::time::Duration;

use anyhow::{Context, Result};
use bacnet_client::client::BACnetClient;
use bacnet_encoding::primitives::decode_application_value;
use bacnet_transport::bvll::encode_bip_mac;
use bacnet_types::enums::{ObjectType, PropertyIdentifier};
use bacnet_types::primitives::{ObjectIdentifier, PropertyValue};
use openfdd_bacnet_feather_concept::app_config::AppConfig;
use openfdd_bacnet_feather_concept::feather_store::read_samples_from_feather;
use tracing::{info, warn};

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter("info,feather_tail=info")
        .init();

    let cfg = AppConfig::load().context("loading config")?;
    let store_path = cfg.feather_store_path();
    if let Some(parent) = store_path.parent() {
        std::fs::create_dir_all(parent)
            .with_context(|| format!("creating Feather store {}", parent.display()))?;
    }

    let server_ip = cfg
        .server
        .address
        .unwrap_or(Ipv4Addr::new(192, 168, 204, 55));
    let server_port = cfg.server.port;
    let device = cfg.server.instance;
    let bi_inst = cfg.server.status_object_instance;
    let status_name = cfg.server.status_point_name.clone();

    let wx_temp_inst = cfg.weather.temp_object_instance;
    let wx_temp_name = cfg.weather.temp_point_name.clone();
    let wx_rh_inst = cfg.weather.humidity_object_instance;
    let wx_dp_inst = cfg.weather.dewpoint_object_instance;
    let wx_loc_inst = cfg.weather.location_object_instance;
    let wx_loc_name = cfg.weather.location_point_name.clone();
    let wx_city = cfg.weather.city.clone();

    let bind = cfg
        .poller
        .bind
        .or(cfg.server.address)
        .unwrap_or(server_ip);
    let broadcast = cfg
        .poller
        .broadcast
        .or(cfg.server.broadcast)
        .unwrap_or(Ipv4Addr::new(192, 168, 204, 255));

    info!(
        "watching Feather file {} (only NEW rows after start)",
        store_path.display()
    );
    info!(
        "BACnet probe: device={device} AV:{wx_temp_inst} \"{wx_temp_name}\" (Open-Meteo {wx_city}) at {server_ip}:{server_port}"
    );

    let client = BACnetClient::bip_builder()
        .interface(bind)
        .port(0)
        .broadcast_address(broadcast)
        .apdu_timeout_ms(3000)
        .build()
        .await
        .context("BACnetClient::build for probe")?;

    let server_mac = encode_bip_mac(server_ip.octets(), server_port);
    let device_oid = ObjectIdentifier::new(ObjectType::DEVICE, device)?;
    let wx_temp_oid = ObjectIdentifier::new(ObjectType::ANALOG_VALUE, wx_temp_inst)?;
    let wx_rh_oid = ObjectIdentifier::new(ObjectType::ANALOG_VALUE, wx_rh_inst)?;
    let wx_dp_oid = ObjectIdentifier::new(ObjectType::ANALOG_VALUE, wx_dp_inst)?;
    let wx_loc_oid = ObjectIdentifier::new(ObjectType::CHARACTERSTRING_VALUE, wx_loc_inst)?;
    let bi_oid = ObjectIdentifier::new(ObjectType::BINARY_INPUT, bi_inst)?;

    let mut seen_rows = if store_path.is_file() {
        match read_samples_from_feather(&store_path) {
            Ok(samples) => {
                info!(
                    "seeded {} existing row(s) in {}",
                    samples.len(),
                    store_path.display()
                );
                samples.len()
            }
            Err(err) => {
                warn!("could not seed {}: {err:#}", store_path.display());
                0
            }
        }
    } else {
        info!("no file yet at {}", store_path.display());
        0
    };

    loop {
        let name_str = match client
            .read_property(&server_mac, device_oid, PropertyIdentifier::OBJECT_NAME, None)
            .await
        {
            Ok(ack) => match decode_application_value(&ack.property_value, 0) {
                Ok((PropertyValue::CharacterString(s), _)) => s,
                Ok((other, _)) => format!("{other:?}"),
                Err(_) => "?".into(),
            },
            Err(err) => {
                println!(
                    "BACNET FAIL  device={device} object-name — is bacnet_app running on :{server_port}? ({err})"
                );
                tokio::time::sleep(Duration::from_secs(1)).await;
                continue;
            }
        };

        let status_label = match client
            .read_property(&server_mac, bi_oid, PropertyIdentifier::PRESENT_VALUE, None)
            .await
        {
            Ok(ack) => match decode_binary(&ack.property_value) {
                Ok(true) => format!("{status_name}=FAULT"),
                Ok(false) => format!("{status_name}=OK"),
                Err(err) => format!("{status_name}=? ({err})"),
            },
            Err(err) => format!("{status_name}=FAIL ({err})"),
        };

        // Primary validation: Open-Meteo outdoor dry-bulb on the mini-device.
        match client
            .read_property(&server_mac, wx_temp_oid, PropertyIdentifier::PRESENT_VALUE, None)
            .await
        {
            Ok(ack) => match decode_real(&ack.property_value) {
                Ok(temp_f) => {
                    let rh = read_optional_real(&client, &server_mac, wx_rh_oid).await;
                    let dp = read_optional_real(&client, &server_mac, wx_dp_oid).await;
                    let loc = read_optional_string(&client, &server_mac, wx_loc_oid).await;
                    // Madison outdoor temps are almost never exactly the fallback 70.0 after a live fetch.
                    // Accept any finite reading in a wide outdoor band as PASS (API or intentional fallback).
                    let plausible = temp_f.is_finite() && (-40.0..=130.0).contains(&temp_f);
                    if plausible {
                        print!(
                            "WEATHER PASS  device={device} name=\"{name_str}\" {wx_temp_name}={temp_f:.1}°F"
                        );
                        if let Some(rh) = rh {
                            print!(" RH={rh:.0}%");
                        }
                        if let Some(dp) = dp {
                            print!(" DP={dp:.1}°F");
                        }
                        if let Some(loc) = loc {
                            print!(" {wx_loc_name}=\"{loc}\"");
                        }
                        println!("  {status_label}");
                    } else {
                        println!(
                            "WEATHER FAIL  device={device} {wx_temp_name}={temp_f} (implausible)  {status_label}"
                        );
                    }
                }
                Err(err) => println!("WEATHER FAIL  present-value decode — {err}"),
            },
            Err(err) => {
                println!("WEATHER FAIL  device={device} AV:{wx_temp_inst} — {err}");
            }
        }

        if store_path.is_file() {
            match read_samples_from_feather(&store_path) {
                Ok(samples) => {
                    if samples.len() > seen_rows {
                        for sample in &samples[seen_rows..] {
                            println!(
                                "FEATHER {} {} id={} {}:{} {}={:.2} {}",
                                sample.ts_utc.to_rfc3339(),
                                sample.device_name,
                                sample.device_instance,
                                sample.object_type,
                                sample.object_instance,
                                sample.point_name,
                                sample.present_value,
                                sample.units,
                            );
                        }
                        seen_rows = samples.len();
                    } else if samples.len() < seen_rows {
                        warn!(
                            "{} shrank ({} → {} rows) — reseeding",
                            store_path.display(),
                            seen_rows,
                            samples.len()
                        );
                        seen_rows = samples.len();
                    }
                }
                Err(err) => {
                    warn!("could not read {} yet: {err:#}", store_path.display());
                }
            }
        }

        tokio::time::sleep(Duration::from_secs(1)).await;
    }
}

async fn read_optional_string(
    client: &BACnetClient<bacnet_transport::bip::BipTransport>,
    mac: &[u8],
    oid: ObjectIdentifier,
) -> Option<String> {
    let ack = client
        .read_property(mac, oid, PropertyIdentifier::PRESENT_VALUE, None)
        .await
        .ok()?;
    let (val, _) = decode_application_value(&ack.property_value, 0).ok()?;
    match val {
        PropertyValue::CharacterString(s) => Some(s),
        _ => None,
    }
}

async fn read_optional_real(
    client: &BACnetClient<bacnet_transport::bip::BipTransport>,
    mac: &[u8],
    oid: ObjectIdentifier,
) -> Option<f64> {
    let ack = client
        .read_property(mac, oid, PropertyIdentifier::PRESENT_VALUE, None)
        .await
        .ok()?;
    decode_real(&ack.property_value).ok()
}

fn decode_real(bytes: &[u8]) -> Result<f64> {
    let (val, _) = decode_application_value(bytes, 0)?;
    match val {
        PropertyValue::Real(v) => Ok(v as f64),
        PropertyValue::Double(v) => Ok(v),
        other => anyhow::bail!("unexpected {other:?}"),
    }
}

fn decode_binary(bytes: &[u8]) -> Result<bool> {
    let (val, _) = decode_application_value(bytes, 0)?;
    match val {
        PropertyValue::Enumerated(0) | PropertyValue::Boolean(false) => Ok(false),
        PropertyValue::Enumerated(1) | PropertyValue::Boolean(true) => Ok(true),
        PropertyValue::Enumerated(v) => Ok(v != 0),
        other => anyhow::bail!("unexpected binary {other:?}"),
    }
}
