//! BAS auto-scan: Who-Is a device-instance range, enumerate points, write AI-editable drivers.
//!
//! Inspired by rusty-bacnet samples `whois-scan` + `point-discover`.
//!
//! ```text
//! # While bacnet_app owns :47808, use --ephemeral
//! cargo run --release --bin bas_scan -- --low 1 --high 4194302 --ephemeral --merge
//!
//! # Apply an AI-edited catalog markdown back to per-device driver files
//! cargo run --release --bin bas_scan -- --apply-catalog config/drivers/catalog.md
//! ```

use std::net::Ipv4Addr;
use std::path::PathBuf;
use std::time::Duration;

use anyhow::{Context, Result};
use bacnet_client::client::BACnetClient;
use bacnet_client::discovery::DiscoveredDevice;
use bacnet_encoding::primitives::decode_application_value;
use bacnet_services::who_is::WhoIsRequest;
use bacnet_transport::bip::DEFAULT_BACNET_PORT;
use bacnet_types::enums::{ObjectType, PropertyIdentifier, UnconfirmedServiceChoice};
use bacnet_types::primitives::{ObjectIdentifier, PropertyValue};
use bytes::BytesMut;
use clap::Parser;
use openfdd_bacnet_feather_concept::app_config::{AppConfig, DeviceConfig, DevicePointConfig};
use openfdd_bacnet_feather_concept::drivers_file::{
    extract_toml_from_catalog, load_devices_from_dir, merge_enabled_flags, write_drivers_bundle,
    DriversFile, DEFAULT_CATALOG_PATH, DEFAULT_DEVICES_DIR, DEFAULT_SETTINGS_PATH,
};
use openfdd_bacnet_feather_concept::network::{resolve_poller_bind, subnet_broadcast};

#[derive(Parser, Debug)]
#[command(
    name = "bas_scan",
    about = "Who-Is scan → per-device TOMLs in config/drivers/devices/ for bacnet_app poller"
)]
struct Args {
    /// Device instance range low (inclusive)
    #[arg(long, default_value_t = 1)]
    low: u32,

    /// Device instance range high (inclusive)
    #[arg(long, default_value_t = 4_194_302)]
    high: u32,

    /// Local NIC IPv4 (default: from config.toml / enp3s0)
    #[arg(long, short = 'i')]
    interface: Option<Ipv4Addr>,

    /// Directed broadcast (default: /24 from interface)
    #[arg(long, short = 'b')]
    broadcast: Option<Ipv4Addr>,

    /// Seconds to wait for I-Am replies
    #[arg(long, short = 't', default_value_t = 4)]
    timeout: u64,

    /// Bind ephemeral UDP port (bacnet_app can stay up; may miss broadcast I-Am)
    #[arg(long)]
    ephemeral: bool,

    /// Bind UDP 47808 (recommended — stop bacnet_app first so broadcast I-Am is received)
    #[arg(long, default_value_t = true)]
    on_bac0: bool,

    /// Skip these device instances (comma-separated). Default includes local mini-device.
    #[arg(long, value_delimiter = ',')]
    skip: Vec<u32>,

    /// Do not auto-skip server.instance from config.toml
    #[arg(long)]
    include_local_server: bool,

    /// Preserve enabled=false / critical / renames from existing device files
    #[arg(long, default_value_t = true)]
    merge: bool,

    /// Overwrite without merging previous enabled flags
    #[arg(long)]
    no_merge: bool,

    /// Default poll interval for new devices
    #[arg(long, default_value_t = 10)]
    interval_secs: u64,

    /// Per-device driver directory (one `<instance>-<name>.toml` per device)
    #[arg(long, default_value = DEFAULT_DEVICES_DIR)]
    devices_dir: PathBuf,

    /// Scan metadata file (comments only — not polled)
    #[arg(long, default_value = DEFAULT_SETTINGS_PATH)]
    settings: PathBuf,

    /// AI catalog markdown path
    #[arg(long, default_value = DEFAULT_CATALOG_PATH)]
    catalog: PathBuf,

    /// Apply an edited catalog markdown → device files (no network scan)
    #[arg(long)]
    apply_catalog: Option<PathBuf>,
}

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter("info,bas_scan=info")
        .init();

    let args = Args::parse();

    if let Some(catalog) = &args.apply_catalog {
        return apply_catalog(catalog, &args.devices_dir, &args.settings, &args.catalog);
    }

    if args.low > args.high {
        anyhow::bail!("--low must be <= --high");
    }

    let site = AppConfig::load().unwrap_or_default();
    let bind = args.interface.unwrap_or_else(|| {
        resolve_poller_bind(site.poller.bind, site.server.address, &site.server.nic)
    });
    let broadcast = args
        .broadcast
        .or(site.poller.broadcast)
        .or(site.server.broadcast)
        .unwrap_or_else(|| subnet_broadcast(bind));

    let mut skip: Vec<u32> = args.skip.clone();
    if !args.include_local_server {
        skip.push(site.server.instance);
    }
    skip.sort_unstable();
    skip.dedup();

    let bind_port = if args.ephemeral {
        0
    } else if args.on_bac0 {
        DEFAULT_BACNET_PORT
    } else {
        DEFAULT_BACNET_PORT
    };

    eprintln!(
        "bas_scan: Who-Is {}..{} bind={bind}:{bind_port} broadcast={broadcast} skip={skip:?}",
        args.low, args.high
    );

    let mut client = BACnetClient::bip_builder()
        .interface(bind)
        .port(bind_port)
        .broadcast_address(broadcast)
        .apdu_timeout_ms(8000)
        .build()
        .await
        .context("BACnetClient::build")?;

    let whois = WhoIsRequest {
        low_limit: Some(args.low),
        high_limit: Some(args.high),
    };
    let mut whois_buf = BytesMut::new();
    whois.encode(&mut whois_buf);

    eprintln!("Sending local-subnet Who-Is...");
    client
        .broadcast_unconfirmed(UnconfirmedServiceChoice::WHO_IS, &whois_buf)
        .await
        .context("local Who-Is")?;

    eprintln!("Sending global Who-Is (DNET=0xFFFF)...");
    client
        .who_is(Some(args.low), Some(args.high))
        .await
        .context("global Who-Is")?;

    tokio::time::sleep(Duration::from_secs(args.timeout.max(1))).await;

    let mut devices = client.discovered_devices().await;
    devices.sort_by_key(|d| d.object_identifier.instance_number());
    devices.dedup_by_key(|d| d.object_identifier.instance_number());

    eprintln!("Discovered {} device(s) in range", devices.len());

    let mut drivers = Vec::new();
    let mut offset: u64 = 0;
    for disc in &devices {
        let instance = disc.object_identifier.instance_number();
        if skip.contains(&instance) {
            eprintln!("  skip device {instance} (local / --skip)");
            continue;
        }
        match discover_driver(&client, disc, args.interval_secs, offset).await {
            Ok(driver) => {
                eprintln!(
                    "  device {instance} \"{}\" @ {}:{} points={}",
                    driver.name,
                    driver.host,
                    driver.port,
                    driver.points.len()
                );
                drivers.push(driver);
                offset = offset.saturating_add(2);
            }
            Err(err) => {
                eprintln!("  WARN: device {instance} — {err:#}");
            }
        }
    }

    let _ = client.stop().await;

    if drivers.is_empty() {
        anyhow::bail!("no pollable devices found — check range, NIC, and that targets answer Who-Is");
    }

    let merge = args.merge && !args.no_merge;
    let previous = if merge {
        load_previous_devices(&args.devices_dir)
    } else {
        Vec::new()
    };
    let drivers = if merge && !previous.is_empty() {
        eprintln!(
            "Merging enabled flags from {} prior device(s)",
            previous.len()
        );
        merge_enabled_flags(drivers, &previous)
    } else {
        drivers
    };

    let header = format!(
        "generated_by = bas_scan\nrange = {}..{}\nbind = {bind}\nbroadcast = {broadcast}\ndevices = {}\n",
        args.low,
        args.high,
        drivers.len()
    );
    write_drivers_bundle(
        &drivers,
        &args.devices_dir,
        &args.settings,
        &args.catalog,
        &header,
    )?;
    eprintln!(
        "\nWrote {} device driver(s) to {}:",
        drivers.len(),
        args.devices_dir.display()
    );
    for d in &drivers {
        eprintln!(
            "  {} — {} (instance {})",
            openfdd_bacnet_feather_concept::drivers_file::device_filename(d),
            d.name,
            d.device_instance
        );
    }
    eprintln!(
        "  {}\n  {}\nRestart bacnet_app to poll into data/feather_store/telemetry.feather",
        args.settings.display(),
        args.catalog.display()
    );
    Ok(())
}

fn load_previous_devices(devices_dir: &PathBuf, legacy: &PathBuf) -> Vec<DeviceConfig> {
    if let Ok(devs) = load_devices_from_dir(devices_dir) {
        if !devs.is_empty() {
            return devs;
        }
    }
    if legacy.is_file() {
        if let Ok(file) = DriversFile::load(legacy) {
            return file.devices;
        }
    }
    Vec::new()
}

fn apply_catalog(
    catalog: &PathBuf,
    devices_dir: &PathBuf,
    settings: &PathBuf,
    catalog_out: &PathBuf,
) -> Result<()> {
    let md = std::fs::read_to_string(catalog)
        .with_context(|| format!("reading catalog {}", catalog.display()))?;
    let toml_text = extract_toml_from_catalog(&md)?;
    let file: DriversFile =
        toml::from_str(&toml_text).context("parsing TOML fence from catalog")?;
    if file.devices.is_empty() {
        anyhow::bail!("catalog TOML has no [[devices]]");
    }
    let header = format!(
        "applied_from = {}\ndevices = {}\n",
        catalog.display(),
        file.devices.len()
    );
    write_drivers_bundle(
        &file.devices,
        devices_dir,
        settings,
        catalog_out,
        &header,
    )?;
    eprintln!(
        "Applied catalog → {} ({} device file(s))",
        devices_dir.display(),
        file.devices.len()
    );
    Ok(())
}

async fn discover_driver(
    client: &BACnetClient<bacnet_transport::bip::BipTransport>,
    disc: &DiscoveredDevice,
    interval_secs: u64,
    offset_secs: u64,
) -> Result<DeviceConfig> {
    let instance = disc.object_identifier.instance_number();
    let (host, port) = bip_endpoint(disc.mac_address.as_slice())
        .with_context(|| format!("device {instance} has non-BIP MAC"))?;

    let (mstp_network, mstp_mac) = match (&disc.source_network, &disc.source_address) {
        (Some(net), Some(mac)) if !mac.is_empty() => (Some(*net), Some(mac.to_vec())),
        _ => (None, None),
    };

    let device_oid = ObjectIdentifier::new(ObjectType::DEVICE, instance)?;
    let name = read_object_name(client, instance, device_oid)
        .await
        .unwrap_or_else(|| format!("device-{instance}"));

    let oids = read_object_list(client, instance, device_oid).await?;
    let mut points = Vec::new();
    for oid in oids {
        if !is_pollable(oid.object_type()) {
            continue;
        }
        let point_name = read_object_name(client, instance, oid)
            .await
            .unwrap_or_else(|| {
                format!(
                    "{}-{}",
                    object_type_slug(oid.object_type()),
                    oid.instance_number()
                )
            });
        points.push(DevicePointConfig {
            enabled: true,
            object_type: object_type_slug(oid.object_type()),
            object_instance: oid.instance_number(),
            point_name,
            units: String::new(),
        });
    }

    if points.is_empty() {
        anyhow::bail!("no pollable points on object-list");
    }

    // Devices with DUCT-T are good APP-FAULT critical candidates.
    let critical = points
        .iter()
        .any(|p| p.point_name.eq_ignore_ascii_case("DUCT-T"));

    Ok(DeviceConfig {
        name: sanitize_name(&name),
        enabled: true,
        device_instance: instance,
        host,
        port,
        mstp_network,
        mstp_mac,
        interval_secs: Some(interval_secs),
        offset_secs,
        critical,
        points,
    })
}

fn is_pollable(ot: ObjectType) -> bool {
    matches!(
        ot,
        ObjectType::ANALOG_INPUT
            | ObjectType::ANALOG_OUTPUT
            | ObjectType::ANALOG_VALUE
            | ObjectType::BINARY_INPUT
            | ObjectType::BINARY_OUTPUT
            | ObjectType::BINARY_VALUE
            | ObjectType::MULTI_STATE_INPUT
            | ObjectType::MULTI_STATE_OUTPUT
            | ObjectType::MULTI_STATE_VALUE
    )
}

fn object_type_slug(ot: ObjectType) -> String {
    match ot {
        ObjectType::ANALOG_INPUT => "analog-input",
        ObjectType::ANALOG_OUTPUT => "analog-output",
        ObjectType::ANALOG_VALUE => "analog-value",
        ObjectType::BINARY_INPUT => "binary-input",
        ObjectType::BINARY_OUTPUT => "binary-output",
        ObjectType::BINARY_VALUE => "binary-value",
        ObjectType::MULTI_STATE_INPUT => "multi-state-input",
        ObjectType::MULTI_STATE_OUTPUT => "multi-state-output",
        ObjectType::MULTI_STATE_VALUE => "multi-state-value",
        _ => "unknown",
    }
    .into()
}

fn sanitize_name(name: &str) -> String {
    let s: String = name
        .chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() || c == '-' || c == '_' {
                c
            } else if c.is_whitespace() {
                '-'
            } else {
                '_'
            }
        })
        .collect();
    let s = s.trim_matches('-').to_string();
    if s.is_empty() {
        "device".into()
    } else {
        s
    }
}

fn bip_endpoint(mac: &[u8]) -> Option<(Ipv4Addr, u16)> {
    if mac.len() == 6 {
        Some((
            Ipv4Addr::new(mac[0], mac[1], mac[2], mac[3]),
            u16::from_be_bytes([mac[4], mac[5]]),
        ))
    } else {
        None
    }
}

fn decode_prop(bytes: &[u8]) -> Option<PropertyValue> {
    decode_application_value(bytes, 0)
        .ok()
        .map(|(v, _)| v)
}

fn decode_object_identifier_list(bytes: &[u8]) -> Vec<ObjectIdentifier> {
    let mut oids = Vec::new();
    let mut offset = 0usize;
    while offset < bytes.len() {
        match decode_application_value(bytes, offset) {
            Ok((PropertyValue::ObjectIdentifier(oid), next)) if next > offset => {
                oids.push(oid);
                offset = next;
            }
            Ok((_, next)) if next > offset => offset = next,
            _ => break,
        }
    }
    oids
}

async fn read_object_name(
    client: &BACnetClient<bacnet_transport::bip::BipTransport>,
    device_instance: u32,
    oid: ObjectIdentifier,
) -> Option<String> {
    let ack = client
        .read_property_from_device(device_instance, oid, PropertyIdentifier::OBJECT_NAME, None)
        .await
        .ok()?;
    match decode_prop(&ack.property_value)? {
        PropertyValue::CharacterString(s) => Some(s),
        _ => None,
    }
}

async fn read_object_list(
    client: &BACnetClient<bacnet_transport::bip::BipTransport>,
    device_instance: u32,
    device_oid: ObjectIdentifier,
) -> Result<Vec<ObjectIdentifier>> {
    async fn read_prop(
        client: &BACnetClient<bacnet_transport::bip::BipTransport>,
        device_instance: u32,
        device_oid: ObjectIdentifier,
        index: Option<u32>,
    ) -> Result<bacnet_services::read_property::ReadPropertyACK> {
        client
            .read_property_from_device(
                device_instance,
                device_oid,
                PropertyIdentifier::OBJECT_LIST,
                index,
            )
            .await
            .map_err(|e| anyhow::anyhow!("{e}"))
    }

    if let Ok(ack0) = read_prop(client, device_instance, device_oid, Some(0)).await {
        if let Some(PropertyValue::Unsigned(count)) = decode_prop(&ack0.property_value) {
            let count = count as u32;
            let mut oids = Vec::with_capacity(count as usize);
            for idx in 1..=count {
                let ack = read_prop(client, device_instance, device_oid, Some(idx)).await?;
                if let Some(PropertyValue::ObjectIdentifier(oid)) = decode_prop(&ack.property_value)
                {
                    oids.push(oid);
                }
            }
            if !oids.is_empty() {
                return Ok(oids);
            }
        }
    }

    let ack = read_prop(client, device_instance, device_oid, None).await?;
    let oids = decode_object_identifier_list(&ack.property_value);
    if oids.is_empty() {
        anyhow::bail!("object-list empty");
    }
    Ok(oids)
}
