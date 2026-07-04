//! Terminal 1: mini-device + updater + poller/Feather writer.

use anyhow::{Context, Result};
use openfdd_bacnet_feather_concept::app_config::AppConfig;
use openfdd_bacnet_feather_concept::{mini_device, poller};
use tracing::{error, info};

/// BACnet writer app.
///
/// ```text
/// cargo run --bin bacnet_app
/// ```
///
/// One process:
/// 1. BACnet/IP mini-device (default UDP **47809** — leaves OT/Open-FDD on 47808)
/// 2. Server value updater (AI:1 every 2s)
/// 3. Poller (ReadProperty every 10s)
/// 4. Atomic Feather publisher (`.tmp` → `.feather`)
#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            "info,bacnet_app=info,openfdd_bacnet_feather_concept=info,bacnet_server=warn,bacnet_client=warn,bacnet_transport=warn",
        )
        .init();

    let cfg = AppConfig::load().context("loading config")?;
    info!("starting Open-FDD BACnet → Feather writer concept");
    info!(
        "store={} server_enabled={} server_port={}",
        cfg.feather_store_folder().display(),
        cfg.server.enabled,
        cfg.server.port
    );

    run_all_writer_tasks_until_ctrl_c(cfg).await
}

async fn run_all_writer_tasks_until_ctrl_c(cfg: AppConfig) -> Result<()> {
    let mut mini_device = if cfg.server.enabled {
        Some(
            mini_device::MiniDeviceRuntime::start(&cfg.server)
                .await
                .context("starting BACnet mini-device runtime")?,
        )
    } else {
        info!("server.enabled=false — poller-only mode (field points from TOML)");
        None
    };

    // Grace period so UDP is listening before first poll.
    tokio::time::sleep(std::time::Duration::from_secs(2)).await;

    let poller_task = {
        let cfg = cfg.clone();
        tokio::spawn(async move { poller::run_poller_forever(cfg).await })
    };

    tokio::select! {
        _ = tokio::signal::ctrl_c() => {
            info!("Ctrl+C received; shutting down BACnet writer app");
        }
        result = poller_task => {
            match result {
                Ok(Ok(())) => error!("poller task ended unexpectedly"),
                Ok(Err(err)) => error!("poller task failed: {err:#}"),
                Err(err) => error!("poller task panicked/join failed: {err:#}"),
            }
        }
    }

    if let Some(mut rt) = mini_device.take() {
        rt.shutdown().await;
    }
    info!("shutdown complete");
    Ok(())
}
