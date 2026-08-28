//! MS/TP probe — loopback acceptance (CI) or hardware acceptance over USB RS-485.

use std::path::PathBuf;

use anyhow::{Context, Result};
use clap::{Parser, Subcommand};
use mstp_lab::{
    run_hardware_acceptance, run_loopback_acceptance, AcceptanceOptions, AcceptanceReport,
};
use tracing::info;

#[derive(Parser, Debug)]
#[command(name = "mstp-probe", about = "Phase 2 MS/TP acceptance probe")]
struct Args {
    #[command(subcommand)]
    command: Command,
    #[arg(long, default_value_t = 123_001)]
    device_instance: u32,
    #[arg(long, default_value = "0")]
    probe_mac: u8,
    #[arg(long, default_value = "1")]
    device_mac: u8,
    #[arg(long, default_value_t = 38400)]
    baud: u32,
    #[arg(long, default_value_t = 10)]
    repeated_reads: u32,
    #[arg(long, default_value = "captures/mstp-acceptance.json")]
    report: PathBuf,
}

#[derive(Subcommand, Debug)]
enum Command {
    /// CI-safe loopback acceptance (no serial hardware).
    Loopback,
    /// Hardware acceptance — device must run separately on `--device-serial`.
    Hardware {
        #[arg(long)]
        probe_serial: String,
        #[arg(long)]
        device_serial: String,
    },
}

fn options(args: &Args) -> AcceptanceOptions {
    AcceptanceOptions {
        device_instance: args.device_instance,
        probe_mac: args.probe_mac,
        device_mac: args.device_mac,
        baud: args.baud,
        repeated_reads: args.repeated_reads,
    }
}

fn write_report(path: &PathBuf, report: &AcceptanceReport) -> Result<()> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).context("create report directory")?;
    }
    std::fs::write(path, serde_json::to_string_pretty(report)?).context("write report")?;
    Ok(())
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
    let opts = options(&args);

    let report = match args.command {
        Command::Loopback => {
            info!("Running MS/TP loopback acceptance");
            run_loopback_acceptance(opts).await
        }
        Command::Hardware {
            probe_serial,
            device_serial: _,
        } => {
            info!("Running MS/TP hardware acceptance on probe={probe_serial}");
            run_hardware_acceptance(&probe_serial, opts).await
        }
    };

    write_report(&args.report, &report)?;
    info!(
        "Acceptance {} — passed {} failed {} → {}",
        report.status,
        report.passed,
        report.failed,
        args.report.display()
    );

    if report.status != "Passed" {
        anyhow::bail!("acceptance failed");
    }
    Ok(())
}
