//! Terminal 1: mimic-style BACnet server (5000) + field poller (5007 AI:1192) + Feather.

use anyhow::{Context, Result};
use openfdd_bacnet_feather_concept::app_config::AppConfig;
use openfdd_bacnet_feather_concept::latest;
use openfdd_bacnet_feather_concept::{mini_device, poller};
use tracing::{error, info};

/// Enhanced openfdd-bacnet-mimic:
/// - Same BIP stack / Who-Is→I-Am / object-list pattern (Workbench-friendly)
/// - Device **5000** named **openfdd-bacnet-feather-concept** on UDP **47808**
/// - Polls field **5007 AI:1192 (DUCT-T)** → Feather + clone AV:1
#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            "info,bacnet_app=info,openfdd_bacnet_feather_concept=info,bacnet_server=warn,bacnet_client=warn,bacnet_transport=warn",
        )
        .init();

    let cfg = AppConfig::load().context("loading config")?;
    info!("starting openfdd-bacnet-feather-concept (mimic-style BIP server)");
    info!(
        "store={} device={} \"{}\" UDP :{} clone=\"{}\"",
        cfg.feather_store_folder().display(),
        cfg.server.instance,
        cfg.server.name,
        cfg.server.port,
        cfg.server.temp_point_name
    );

    run_all_writer_tasks_until_ctrl_c(cfg).await
}

async fn run_all_writer_tasks_until_ctrl_c(cfg: AppConfig) -> Result<()> {
    let latest = latest::new_latest();

    let mut mini_device = if cfg.server.enabled {
        Some(
            mini_device::MiniDeviceRuntime::start(&cfg.server, latest.clone())
                .await
                .context("starting BACnet mini-device runtime")?,
        )
    } else {
        info!("server.enabled=false — poller-only mode");
        None
    };

    // Brief settle before poller binds the same NIC.
    tokio::time::sleep(std::time::Duration::from_secs(1)).await;

    let poller_task = {
        let cfg = cfg.clone();
        let latest = latest.clone();
        tokio::spawn(async move { poller::run_poller_forever(cfg, latest).await })
    };

    tokio::select! {
        _ = tokio::signal::ctrl_c() => {
            info!("Ctrl+C received; shutting down");
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
