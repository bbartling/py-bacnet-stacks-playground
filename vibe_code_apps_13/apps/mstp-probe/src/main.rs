//! MS/TP probe — loopback acceptance (CI) or hardware acceptance over USB RS-485.

use std::path::{Path, PathBuf};

use anyhow::{Context, Result};
use clap::{Parser, Subcommand};
use lab_common::{atomic_write_serde, BaudRate};
use mstp_lab::{
    run_hardware_acceptance, run_loopback_acceptance, AcceptanceOptions, AcceptanceProfile,
    AcceptanceReport, LAB_VENDOR_ID,
};
use tracing::info;

#[derive(Parser, Debug)]
#[command(
    name = "mstp-probe",
    about = "Phase 2 MS/TP acceptance probe",
    after_help = "Global flags must appear BEFORE the subcommand.\nExample: mstp-probe --profile smoke --report captures/out.json loopback"
)]
struct Args {
    #[arg(long, default_value = "smoke")]
    profile: String,
    #[arg(long, default_value_t = 123_001)]
    device_instance: u32,
    #[arg(long, default_value = "0")]
    probe_mac: u8,
    #[arg(long, default_value = "1")]
    device_mac: u8,
    #[arg(long, default_value_t = 38400)]
    baud: u32,
    #[arg(long, default_value = "10")]
    max_master: u8,
    #[arg(long, default_value = "1")]
    max_info_frames: u8,
    #[arg(long, default_value_t = 10)]
    repeated_reads: u32,
    #[arg(long, default_value_t = LAB_VENDOR_ID)]
    vendor_id: u16,
    #[arg(long, default_value = "captures/mstp-acceptance.json")]
    report: PathBuf,
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand, Debug)]
enum Command {
    /// CI-safe loopback acceptance (no serial hardware).
    Loopback,
    /// Hardware acceptance — device must already own `--device-serial` (metadata only).
    Hardware {
        #[arg(long)]
        probe_serial: String,
        /// Report metadata only — probe never opens this tty.
        #[arg(long)]
        device_serial: Option<String>,
    },
}

fn options(args: &Args, command: &Command) -> Result<AcceptanceOptions> {
    let profile: AcceptanceProfile = args.profile.parse().map_err(anyhow::Error::msg)?;
    let baud = BaudRate::try_from(args.baud).map_err(anyhow::Error::msg)?;
    let (probe_serial, device_serial) = match command {
        Command::Loopback => (None, None),
        Command::Hardware {
            probe_serial,
            device_serial,
        } => (Some(probe_serial.clone()), device_serial.clone()),
    };
    let opts = AcceptanceOptions {
        profile,
        device_instance: args.device_instance,
        probe_mac: args.probe_mac,
        device_mac: args.device_mac,
        baud,
        max_master: args.max_master,
        max_info_frames: args.max_info_frames,
        repeated_reads: args.repeated_reads,
        vendor_id: args.vendor_id,
        probe_serial,
        device_serial,
    };
    Ok(opts)
}

fn write_report(path: &Path, report: &AcceptanceReport) -> Result<()> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).context("create report directory")?;
    }
    atomic_write_serde(path, report).context("atomic write report")?;
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
    let opts = options(&args, &args.command)?;

    let report = match &args.command {
        Command::Loopback => {
            info!(
                profile = %opts.profile.as_str(),
                baud = opts.baud.as_u32(),
                "Running MS/TP loopback acceptance"
            );
            run_loopback_acceptance(opts).await
        }
        Command::Hardware { .. } => {
            info!(
                profile = %opts.profile.as_str(),
                baud = opts.baud.as_u32(),
                probe = ?opts.probe_serial,
                "Running MS/TP hardware acceptance (probe only)"
            );
            run_hardware_acceptance(opts).await
        }
    };

    write_report(&args.report, &report)?;
    info!(
        "Acceptance {} — passed {} failed {} hardware_evidence={} → {}",
        report.status,
        report.passed,
        report.failed,
        report.hardware_evidence,
        args.report.display()
    );

    if report.status != "Passed" {
        anyhow::bail!("acceptance failed");
    }
    Ok(())
}
