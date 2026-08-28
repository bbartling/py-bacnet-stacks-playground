//! MS/TP-only `BACnet` mini-device (Phase 2). No `BACnet`/IP.

use std::sync::Arc;
use std::time::Duration;

use anyhow::{Context, Result};
use bacnet_objects::database::ObjectDatabase;
use bacnet_server::server::BACnetServer;
use bacnet_types::enums::{ObjectType, PropertyIdentifier};
use bacnet_types::primitives::{ObjectIdentifier, PropertyValue};
use clap::Parser;
use lab_common::{BaudRate, MstpMasterConfig};
use mstp_lab::{
    build_mini_device_database, open_mstp_transport, MiniDeviceConfig, VENDOR_ID, UNITS_DEGF,
};
use tokio::sync::RwLock;
use tracing::info;

#[derive(Parser, Debug)]
#[command(name = "mstp-mini-device", about = "Phase 2 MS/TP-only BACnet mini device")]
struct Args {
    #[arg(long)]
    serial: String,
    #[arg(long, default_value_t = 38400)]
    baud: u32,
    #[arg(long, default_value = "1")]
    mac: u8,
    #[arg(long, default_value = "10")]
    max_master: u8,
    #[arg(long, default_value = "1")]
    max_info_frames: u8,
    #[arg(long, default_value_t = 123_001)]
    device_instance: u32,
    #[arg(long, default_value = "Rust MS/TP Mini Device")]
    name: String,
    #[arg(long, default_value_t = VENDOR_ID)]
    vendor_id: u16,
}

fn master_config(args: &Args) -> Result<MstpMasterConfig> {
    let cfg = MstpMasterConfig {
        serial_path: args.serial.clone(),
        baud: BaudRate::try_from(args.baud).map_err(anyhow::Error::msg)?,
        mac: args.mac,
        max_master: args.max_master,
        max_info_frames: args.max_info_frames,
    };
    cfg.validate().map_err(anyhow::Error::msg)?;
    Ok(cfg)
}

async fn simulation_task(db: Arc<RwLock<ObjectDatabase>>) {
    let ai_oid = ObjectIdentifier::new(ObjectType::ANALOG_INPUT, 1).expect("ai:1");
    let bi_oid = ObjectIdentifier::new(ObjectType::BINARY_INPUT, 1).expect("bi:1");
    let samples: [(bool, f32); 4] = [(true, 1.0), (false, 2.0), (true, 3.0), (false, 4.0)];
    let mut idx = 0usize;
    loop {
        tokio::time::sleep(Duration::from_secs(5)).await;
        let (active, av_val) = samples[idx];
        idx = (idx + 1) % samples.len();
        let mut db = db.write().await;
        if let Some(obj) = db.get_mut(&ai_oid) {
            let _ = obj.write_property(
                PropertyIdentifier::PRESENT_VALUE,
                None,
                PropertyValue::Real(av_val),
                None,
            );
        }
        if let Some(obj) = db.get_mut(&bi_oid) {
            let bi_val = u32::from(active);
            let _ = obj.write_property(
                PropertyIdentifier::PRESENT_VALUE,
                None,
                PropertyValue::Enumerated(bi_val),
                None,
            );
        }
    }
}

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("info")),
        )
        .init();

    let args = Args::parse();
    let master = master_config(&args)?;
    let endpoint = open_mstp_transport(&master).context("open MS/TP serial")?;

    let db = build_mini_device_database(&MiniDeviceConfig {
        instance: args.device_instance,
        name: args.name.clone(),
    })?;

    info!(
        "Starting MS/TP mini-device: serial={} mac={} instance={} baud={}",
        args.serial, args.mac, args.device_instance, args.baud
    );

    let mut server = BACnetServer::generic_builder()
        .transport(endpoint.transport)
        .database(db)
        .vendor_id(args.vendor_id)
        .build()
        .await
        .context("start BACnet MS/TP server")?;

    info!(
        "MS/TP device up — MAC {} instance {} (AI:1 BI:1 AV:2 BV:2, units degF={UNITS_DEGF})",
        args.mac, args.device_instance
    );

    let db_arc = Arc::clone(server.database());
    tokio::spawn(simulation_task(db_arc));

    tokio::signal::ctrl_c().await?;
    info!("Shutting down…");
    server.stop().await.context("stop server")?;
    Ok(())
}
