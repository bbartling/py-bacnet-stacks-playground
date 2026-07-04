//! Terminal 2: validate mini-device (BACnet probe) + new Feather shards.
//!
//! ```text
//! cargo run --release --bin feather_tail
//! ```

use std::collections::HashSet;
use std::net::Ipv4Addr;
use std::path::{Path, PathBuf};
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
    let root = cfg.feather_store_folder();
    std::fs::create_dir_all(&root)
        .with_context(|| format!("creating Feather store folder {}", root.display()))?;

    let server_ip = cfg
        .server
        .address
        .unwrap_or(Ipv4Addr::new(192, 168, 204, 55));
    let server_port = cfg.server.port;
    let device = cfg.server.instance;
    let av_inst = cfg.server.temp_object_instance;
    let point_name = cfg.server.temp_point_name.clone();

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

    info!("watching Feather store {} (only NEW shards after start)", root.display());
    info!(
        "BACnet probe: device={device} AV:{av_inst} \"{point_name}\" at {server_ip}:{server_port}"
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
    let av_oid = ObjectIdentifier::new(ObjectType::ANALOG_VALUE, av_inst)?;

    // Ignore history already on disk — only report shards written after we start.
    let mut seen_files: HashSet<PathBuf> = list_completed_feather_files(&root)?
        .into_iter()
        .collect();
    info!("seeded {} existing feather file(s) as seen", seen_files.len());

    let mut last_feather_pv: Option<f64> = None;

    loop {
        // 1) BACnet probe first (mimic bacnet-probe style unicast)
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

        match client
            .read_property(&server_mac, av_oid, PropertyIdentifier::PRESENT_VALUE, None)
            .await
        {
            Ok(ack) => match decode_real(&ack.property_value) {
                Ok(bacnet_pv) => {
                    print!(
                        "BACNET  PASS  device={device} name=\"{name_str}\" {point_name}={bacnet_pv:.2}"
                    );
                    if let Some(feather_pv) = last_feather_pv {
                        let delta = (bacnet_pv - feather_pv).abs();
                        if delta < 0.5 {
                            println!("  |  FEATHER={feather_pv:.2}  MATCH (Δ={delta:.2})");
                        } else {
                            println!(
                                "  |  FEATHER={feather_pv:.2}  DRIFT (Δ={delta:.2}) — wait for next poll"
                            );
                        }
                    } else {
                        println!("  |  FEATHER=(waiting for new shard)");
                    }
                }
                Err(err) => println!("BACNET FAIL  present-value decode — {err}"),
            },
            Err(err) => {
                println!(
                    "BACNET FAIL  device={device} AV:{av_inst} — {err}"
                );
            }
        }

        // 2) New Feather shards only
        for path in list_completed_feather_files(&root)? {
            if seen_files.contains(&path) {
                continue;
            }
            match read_samples_from_feather(&path) {
                Ok(samples) => {
                    for sample in samples {
                        println!(
                            "FEATHER {} device={} {}:{} {}={:.2} {} file={}",
                            sample.ts_utc.to_rfc3339(),
                            sample.device_instance,
                            sample.object_type,
                            sample.object_instance,
                            sample.point_name,
                            sample.present_value,
                            sample.units,
                            path.display(),
                        );
                        last_feather_pv = Some(sample.present_value);
                    }
                    seen_files.insert(path);
                }
                Err(err) => warn!("could not read {} yet: {err:#}", path.display()),
            }
        }

        tokio::time::sleep(Duration::from_secs(1)).await;
    }
}

fn list_completed_feather_files(root: &Path) -> Result<Vec<PathBuf>> {
    let mut files = Vec::new();
    for entry in std::fs::read_dir(root)
        .with_context(|| format!("reading Feather store folder {}", root.display()))?
    {
        let entry = entry?;
        let path = entry.path();
        let is_feather = path
            .extension()
            .and_then(|ext| ext.to_str())
            .is_some_and(|ext| ext.eq_ignore_ascii_case("feather"));
        if is_feather {
            files.push(path);
        }
    }
    files.sort();
    Ok(files)
}

fn decode_real(bytes: &[u8]) -> Result<f64> {
    let (val, _) = decode_application_value(bytes, 0)?;
    match val {
        PropertyValue::Real(v) => Ok(v as f64),
        PropertyValue::Double(v) => Ok(v),
        other => anyhow::bail!("unexpected {other:?}"),
    }
}
