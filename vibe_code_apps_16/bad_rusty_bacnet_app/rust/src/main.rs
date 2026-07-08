//! # bad_bacnet_app — **intentionally broken** BACnet client for PCAP forensics
//!
//! Emulates Open-FDD 802258a failure points documented in:
//!   open-fdd/workspace/reports/BACNET_PCAP_802258A_vs_VIBE16_REPORT.md
//!
//! Anti-patterns implemented ON PURPOSE:
//!   FP-1 Who-Is (0..4194303) before every read
//!   FP-2 build_client() + stop_client() per poll cycle (no shared client)
//!   FP-4 read_property_from_device() for MSTP 5007 (no read_property_routed)
//!   FP-5 optional dual poll loops (bridge + commission simulation)

use std::net::Ipv4Addr;
use std::path::PathBuf;
use std::time::Duration;

use anyhow::{Context, Result};
use bacnet_client::client::BACnetClient;
use bacnet_encoding::primitives::decode_application_value;
use bacnet_transport::bip::BipTransport;
use bacnet_transport::bvll::encode_bip_mac;
use bacnet_types::enums::{ObjectType, PropertyIdentifier};
use bacnet_types::primitives::{ObjectIdentifier, PropertyValue};
use clap::Parser;
use serde::Deserialize;
use tokio::time::{sleep, Instant};
use tracing::{info, warn};

#[derive(Parser)]
#[command(name = "bad_bacnet_app")]
struct Cli {
    #[arg(long, default_value = "../config.toml")]
    config: PathBuf,
    #[arg(long, default_value_t = 90, alias = "duration")]
    duration_secs: u64,
}

#[derive(Debug, Deserialize)]
struct Config {
    bind_ip: String,
    broadcast: String,
    poll_interval_secs: u64,
    whois_low: u32,
    whois_high: u32,
    mstp_network: u16,
    discover_sleep_secs: u64,
    dual_loop: bool,
    loop_offset_secs: u64,
    router_ip: Option<String>,
    targets: Vec<Target>,
}

#[derive(Debug, Deserialize)]
struct Target {
    label: String,
    device_instance: u32,
    host: Option<String>,
    object_type: String,
    object_instance: u32,
}

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter("info,bad_bacnet_app=info,bacnet_client=warn")
        .init();

    let cli = Cli::parse();
    let cfg: Config = toml::from_str(
        &std::fs::read_to_string(&cli.config)
            .with_context(|| format!("read {}", cli.config.display()))?,
    )?;

    warn!("╔══════════════════════════════════════════════════════════════╗");
    warn!("║  BAD BACNET APP — intentional anti-patterns for lab study   ║");
    warn!("║  Will broadcast Who-Is and hammer the OT network. STOP ME.  ║");
    warn!("╚══════════════════════════════════════════════════════════════╝");

    let end = Instant::now() + Duration::from_secs(cli.duration_secs);
    let cfg = std::sync::Arc::new(cfg);

    if cfg.dual_loop {
        info!("starting DUAL bad poll loops (simulates bridge + commission)");
        let c1 = cfg.clone();
        let t1 = tokio::spawn(async move { bad_poll_loop("bridge", &c1, end).await });
        sleep(Duration::from_secs(cfg.loop_offset_secs)).await;
        let c2 = cfg.clone();
        let t2 = tokio::spawn(async move { bad_poll_loop("commission", &c2, end).await });
        let _ = tokio::try_join!(t1, t2);
    } else {
        bad_poll_loop("single", &cfg, end).await?;
    }

    info!("bad_bacnet_app finished after {}s", cli.duration_secs);
    Ok(())
}

async fn bad_poll_loop(name: &str, cfg: &Config, end: Instant) -> Result<()> {
    let interval = Duration::from_secs(cfg.poll_interval_secs.max(5));
    let mut cycle = 0u64;

    while Instant::now() < end {
        cycle += 1;
        info!("[{name}] cycle {cycle} — FP-2 build_client (new socket every time)");
        let mut client = build_ephemeral_client(cfg).await?;

        // FP-1: broadcast Who-Is entire BACnet instance space before every read
        info!(
            "[{name}] FP-1 Who-Is {}..{} → broadcast {}",
            cfg.whois_low, cfg.whois_high, cfg.broadcast
        );
        client
            .who_is(Some(cfg.whois_low), Some(cfg.whois_high))
            .await
            .map_err(|e| anyhow::anyhow!("who_is: {e}"))?;
        let _ = client
            .who_is_network(cfg.mstp_network, Some(cfg.whois_low), Some(cfg.whois_high))
            .await;

        // Extra bad discovery: directed Who-Is to each configured host (still before every read).
        if let Some(router) = &cfg.router_ip {
            if let Ok(ip) = router.parse::<Ipv4Addr>() {
                let mac = encode_bip_mac(ip.octets(), 0xBAC0);
                let _ = client
                    .who_is_directed(&mac, Some(cfg.whois_low), Some(cfg.whois_high))
                    .await;
            }
        }
        for t in &cfg.targets {
            if let Some(host) = &t.host {
                if let Ok(ip) = host.parse::<Ipv4Addr>() {
                    let mac = encode_bip_mac(ip.octets(), 0xBAC0);
                    let _ = client
                        .who_is_directed(&mac, Some(t.device_instance), Some(t.device_instance))
                        .await;
                }
            }
        }

        sleep(Duration::from_secs(cfg.discover_sleep_secs)).await;

        for t in &cfg.targets {
            // FP-4: read_property_from_device for MSTP 5007 — no read_property_routed
            let ot = parse_object_type(&t.object_type)?;
            let oid = ObjectIdentifier::new(ot, t.object_instance)?;
            match client
                .read_property_from_device(
                    t.device_instance,
                    oid,
                    PropertyIdentifier::PRESENT_VALUE,
                    None,
                )
                .await
            {
                Ok(ack) => {
                    if let Ok((val, _)) = decode_application_value(&ack.property_value, 0) {
                        let v = property_value_f64(&val);
                        info!(
                            "[{name}] FP-4 read {} dev={} {}:{} = {v}",
                            t.label, t.device_instance, t.object_type, t.object_instance
                        );
                    }
                }
                Err(err) => {
                    warn!(
                        "[{name}] FP-4 read FAILED {} dev={}: {err}",
                        t.label, t.device_instance
                    );
                }
            }
        }

        // FP-2: destroy client + device table every cycle
        info!("[{name}] FP-2 stop_client — device table discarded");
        let _ = client.stop().await;

        sleep(interval).await;
    }
    Ok(())
}

async fn build_ephemeral_client(cfg: &Config) -> Result<BACnetClient<BipTransport>> {
    let bind: Ipv4Addr = cfg.bind_ip.parse().context("bind_ip")?;
    let bcast: Ipv4Addr = cfg.broadcast.parse().context("broadcast")?;
    BACnetClient::bip_builder()
        .interface(bind)
        .port(0)
        .broadcast_address(bcast)
        .apdu_timeout_ms(6000)
        .build()
        .await
        .context("BACnetClient::build")
}

fn parse_object_type(s: &str) -> Result<ObjectType> {
    match s.to_ascii_lowercase().replace('-', "_").as_str() {
        "analog_input" | "ai" => Ok(ObjectType::ANALOG_INPUT),
        "analog_value" | "av" => Ok(ObjectType::ANALOG_VALUE),
        _ => anyhow::bail!("unsupported object_type {s}"),
    }
}

fn property_value_f64(v: &PropertyValue) -> f64 {
    match v {
        PropertyValue::Real(x) => *x as f64,
        PropertyValue::Unsigned(x) => *x as f64,
        PropertyValue::Signed(x) => *x as f64,
        PropertyValue::Boolean(b) => {
            if *b {
                1.0
            } else {
                0.0
            }
        }
        _ => f64::NAN,
    }
}
