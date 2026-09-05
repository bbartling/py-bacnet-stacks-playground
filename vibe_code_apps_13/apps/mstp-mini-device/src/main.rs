//! MS/TP-only `BACnet` mini-device (Phase 2). No `BACnet`/IP.

use std::path::Path;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::Duration;

use anyhow::{Context, Result};
use bacnet_objects::database::ObjectDatabase;
use bacnet_server::server::BACnetServer;
use clap::Parser;
use lab_common::{BaudRate, MstpMasterConfig};
use mstp_lab::{
    apply_simulated_inputs, build_mini_device_database, open_mstp_transport, MiniDeviceConfig,
    LAB_VENDOR_ID, RUSTY_BACNET_REV, UNITS_DEGF,
};
use tokio::sync::RwLock;
use tracing::{error, info, warn};

#[derive(Parser, Debug)]
#[command(
    name = "mstp-mini-device",
    about = "Phase 2 MS/TP-only BACnet mini device (lab vendor ID is a placeholder)"
)]
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
    /// Lab placeholder vendor ID (default 999) — not production-ready.
    #[arg(long, default_value_t = LAB_VENDOR_ID)]
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

async fn wait_shutdown_signal(shutdown: Arc<AtomicBool>) {
    #[cfg(unix)]
    {
        use tokio::signal::unix::{signal, SignalKind};
        let mut sigterm = signal(SignalKind::terminate()).expect("install SIGTERM handler");
        let mut sigint = signal(SignalKind::interrupt()).expect("install SIGINT handler");
        tokio::select! {
            _ = sigterm.recv() => warn!("SIGTERM — shutting down"),
            _ = sigint.recv() => warn!("SIGINT — shutting down"),
            () = async {
                while !shutdown.load(Ordering::Relaxed) {
                    tokio::time::sleep(Duration::from_secs(1)).await;
                }
                warn!("transport watchdog — shutting down");
            } => {}
        }
    }
    #[cfg(not(unix))]
    {
        let _ = tokio::signal::ctrl_c().await;
        warn!("Ctrl-C — shutting down");
    }
}

async fn serial_watchdog(
    serial_path: String,
    usb_gone: Arc<AtomicBool>,
    shutdown: Arc<AtomicBool>,
) {
    loop {
        tokio::time::sleep(Duration::from_secs(2)).await;
        if !Path::new(&serial_path).exists() {
            error!(path = %serial_path, "serial device path disappeared (USB unplug?)");
            // Latch reason permanently — reappearance during shutdown must not clear exit 75.
            usb_gone.store(true, Ordering::Relaxed);
            shutdown.store(true, Ordering::Relaxed);
            return;
        }
    }
}

async fn simulation_task(db: Arc<RwLock<ObjectDatabase>>) {
    let samples: [(bool, f32); 4] = [(true, 1.0), (false, 2.0), (true, 3.0), (false, 4.0)];
    let mut idx = 0usize;
    loop {
        tokio::time::sleep(Duration::from_secs(5)).await;
        let (active, ai_val) = samples[idx];
        idx = (idx + 1) % samples.len();
        let mut db = db.write().await;
        if let Err(e) = apply_simulated_inputs(&mut db, active, ai_val) {
            error!(
                error = %e,
                object = "AI:1/BI:1",
                property = "Present_Value",
                "simulation update failed — terminating simulation task"
            );
            return;
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
        vendor_id: args.vendor_id,
    })?;

    info!(
        serial = %args.serial,
        baud = args.baud,
        mac = args.mac,
        max_master = args.max_master,
        max_info_frames = args.max_info_frames,
        device_instance = args.device_instance,
        rusty_bacnet_rev = RUSTY_BACNET_REV,
        vendor_id = args.vendor_id,
        "Starting MS/TP mini-device (lab placeholder vendor ID)"
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

    let shutdown = Arc::new(AtomicBool::new(false));
    let usb_gone_latch = Arc::new(AtomicBool::new(false));
    tokio::spawn(serial_watchdog(
        args.serial.clone(),
        Arc::clone(&usb_gone_latch),
        Arc::clone(&shutdown),
    ));

    let db_arc = Arc::clone(server.database());
    tokio::spawn(simulation_task(db_arc));

    // Single recovery owner: path watchdog + exit 75 → systemd Restart=on-failure.
    // Do not layer an in-process reopen loop on top of systemd.
    wait_shutdown_signal(Arc::clone(&shutdown)).await;
    let usb_gone = usb_gone_latch.load(Ordering::Relaxed);
    info!("Shutting down…");
    server.stop().await.context("stop server")?;
    if usb_gone {
        const EXIT_USB_GONE: i32 = 75;
        error!(
            exit = EXIT_USB_GONE,
            "exiting for systemd USB recovery (disappearance latched; path may have returned)"
        );
        std::process::exit(EXIT_USB_GONE);
    }
    Ok(())
}
