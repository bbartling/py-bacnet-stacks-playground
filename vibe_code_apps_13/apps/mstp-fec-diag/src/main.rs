//! One-shot or 1 Hz MS/TP peer diag against a real field device (e.g. JCI FEC).
//! Not the Phase 2 mini-device acceptance profile.
//!
//! Never uses MAC 0 while BASRT is on the bus — pass `--mac` explicitly (e.g. 3).

use std::fs;
use std::path::{Path, PathBuf};
use std::time::Duration;

use anyhow::{bail, Context, Result};
use bacnet_client::client::BACnetClient;
use bacnet_encoding::primitives::decode_application_value;
use bacnet_types::enums::{ObjectType, PropertyIdentifier};
use bacnet_types::primitives::{ObjectIdentifier, PropertyValue};
use clap::Parser;
use lab_common::BaudRate;
use mstp_lab::{master_config, open_mstp_transport, RUSTY_BACNET_REV};
use serde::Serialize;
use tokio::time::{sleep, timeout};
use tracing::{error, info, warn};

#[derive(Parser, Debug)]
#[command(
    name = "mstp-fec-diag",
    about = "Who-Is + ReadProperty on one USB MS/TP adapter"
)]
struct Args {
    #[arg(long)]
    serial: String,
    #[arg(long, default_value_t = 38400)]
    baud: u32,
    /// This station MAC. Required — never default to 0 (BASRT conflict).
    #[arg(long)]
    mac: u8,
    #[arg(long, default_value_t = 127)]
    max_master: u8,
    #[arg(long, default_value_t = 1)]
    max_info_frames: u8,
    #[arg(long, default_value_t = 5007)]
    device_instance: u32,
    #[arg(long, default_value_t = 7)]
    expect_mac: u8,
    #[arg(long, default_value_t = 1173)]
    ai_instance: u32,
    #[arg(long, default_value_t = 8_000)]
    apdu_timeout_ms: u64,
    #[arg(long, default_value_t = 5_000)]
    settle_ms: u64,
    /// If > 0, keep reading `Present_Value` every N seconds (peer soak for Workbench watch).
    #[arg(long, default_value_t = 0)]
    loop_secs: u64,
    /// Stop after this many loop reads (0 = until Ctrl-C / SIGTERM).
    #[arg(long, default_value_t = 0)]
    loop_count: u32,
    /// Write a structured JSON report on exit (success or failure).
    #[arg(long)]
    report: Option<PathBuf>,
}

#[derive(Debug, Serialize)]
struct DiagReport {
    ok: bool,
    serial: String,
    resolved_hint: String,
    baud: u32,
    mac: u8,
    max_master: u8,
    max_info_frames: u8,
    device_instance: u32,
    expect_mac: u8,
    ai_instance: u32,
    rusty_bacnet_rev: String,
    object_name: Option<String>,
    ai_present_value: Option<f32>,
    loop_ok: u32,
    loop_fail: u32,
    error: Option<String>,
}

impl DiagReport {
    fn base(args: &Args) -> Self {
        Self {
            ok: false,
            serial: args.serial.clone(),
            resolved_hint: resolve_hint(&args.serial),
            baud: args.baud,
            mac: args.mac,
            max_master: args.max_master,
            max_info_frames: args.max_info_frames,
            device_instance: args.device_instance,
            expect_mac: args.expect_mac,
            ai_instance: args.ai_instance,
            rusty_bacnet_rev: RUSTY_BACNET_REV.to_owned(),
            object_name: None,
            ai_present_value: None,
            loop_ok: 0,
            loop_fail: 0,
            error: None,
        }
    }
}

fn resolve_hint(serial: &str) -> String {
    fs::canonicalize(serial).map_or_else(|_| serial.to_owned(), |p| p.display().to_string())
}

fn validate_args(args: &Args) -> Result<()> {
    if args.serial.trim().is_empty() {
        bail!("--serial must be non-empty (prefer /dev/serial/by-id/...)");
    }
    let _baud = BaudRate::try_from(args.baud).map_err(anyhow::Error::msg)?;
    if args.max_master > 127 {
        bail!("--max-master {} exceeds 127", args.max_master);
    }
    if args.mac > args.max_master {
        bail!(
            "--mac {} exceeds --max-master {}",
            args.mac,
            args.max_master
        );
    }
    if args.expect_mac > args.max_master {
        bail!(
            "--expect-mac {} exceeds --max-master {}",
            args.expect_mac,
            args.max_master
        );
    }
    if args.mac == args.expect_mac {
        bail!("--mac must differ from --expect-mac (both {})", args.mac);
    }
    if args.max_info_frames == 0 {
        bail!("--max-info-frames must be >= 1");
    }
    Ok(())
}

fn write_report(path: &Path, report: &DiagReport) -> Result<()> {
    if let Some(parent) = path.parent() {
        if !parent.as_os_str().is_empty() {
            fs::create_dir_all(parent).context("create report directory")?;
        }
    }
    let json = serde_json::to_string_pretty(report).context("serialize report")?;
    fs::write(path, json).context("write report")?;
    Ok(())
}

fn finish(report_path: Option<&Path>, report: DiagReport) -> Result<()> {
    if let Some(path) = report_path {
        write_report(path, &report)?;
        info!(path = %path.display(), ok = report.ok, "wrote JSON report");
    }
    if report.ok {
        Ok(())
    } else {
        bail!(report.error.unwrap_or_else(|| "diag failed".into()))
    }
}

#[allow(clippy::too_many_lines)]
#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("info")),
        )
        .init();

    let args = Args::parse();
    let report_path = args.report.clone();
    let mut report = DiagReport::base(&args);

    if let Err(e) = validate_args(&args) {
        report.error = Some(e.to_string());
        return finish(report_path.as_deref(), report);
    }

    let baud = BaudRate::try_from(args.baud).map_err(anyhow::Error::msg)?;
    let cfg = master_config(
        &args.serial,
        args.mac,
        baud,
        args.max_master,
        args.max_info_frames,
    );

    info!(
        serial = %args.serial,
        resolved = %report.resolved_hint,
        baud = baud.as_u32(),
        mac = args.mac,
        max_master = args.max_master,
        max_info_frames = args.max_info_frames,
        target_instance = args.device_instance,
        expect_mac = args.expect_mac,
        rusty_bacnet_rev = RUSTY_BACNET_REV,
        loop_secs = args.loop_secs,
        "Opening MS/TP probe (auto RS-485 direction; no kernel RS485/GPIO DE)"
    );

    let endpoint = match open_mstp_transport(&cfg) {
        Ok(e) => e,
        Err(e) => {
            report.error = Some(format!("open transport: {e:#}"));
            return finish(report_path.as_deref(), report);
        }
    };
    let client = match BACnetClient::generic_builder()
        .transport(endpoint.transport)
        .apdu_timeout_ms(args.apdu_timeout_ms)
        .build()
        .await
    {
        Ok(c) => c,
        Err(e) => {
            report.error = Some(format!("start BACnet client: {e:#}"));
            return finish(report_path.as_deref(), report);
        }
    };

    sleep(Duration::from_millis(args.settle_ms)).await;
    info!("Who-Is for instance {}", args.device_instance);
    if let Err(e) = client
        .who_is(Some(args.device_instance), Some(args.device_instance))
        .await
    {
        report.error = Some(format!("Who-Is: {e:#}"));
        return finish(report_path.as_deref(), report);
    }
    // Token-ring join with Max_Master=127 can be slow; give I-Am time to arrive.
    let iam_wait_ms = args.apdu_timeout_ms.max(8_000);
    info!(iam_wait_ms, "Waiting for I-Am");
    sleep(Duration::from_millis(iam_wait_ms)).await;

    let Some(dev) = client.get_device(args.device_instance).await else {
        report.error = Some(format!(
            "no I-Am for instance {} after Who-Is (token/join or wiring?)",
            args.device_instance
        ));
        return finish(report_path.as_deref(), report);
    };
    let got_mac = dev.mac_address.as_slice();
    info!(
        instance = args.device_instance,
        mac = ?got_mac,
        vendor_id = dev.vendor_id,
        "I-Am observed"
    );
    if got_mac != [args.expect_mac].as_slice() {
        warn!(
            expected = args.expect_mac,
            got = ?got_mac,
            "MAC differs from expect_mac (continuing reads anyway)"
        );
    }

    let mac = got_mac.to_vec();
    let device_oid = match ObjectIdentifier::new(ObjectType::DEVICE, args.device_instance) {
        Ok(o) => o,
        Err(e) => {
            report.error = Some(format!("device oid: {e:#}"));
            return finish(report_path.as_deref(), report);
        }
    };
    let ai_oid = match ObjectIdentifier::new(ObjectType::ANALOG_INPUT, args.ai_instance) {
        Ok(o) => o,
        Err(e) => {
            report.error = Some(format!("ai oid: {e:#}"));
            return finish(report_path.as_deref(), report);
        }
    };

    let name_ack = match timeout(
        Duration::from_secs(30),
        client.read_property(&mac, device_oid, PropertyIdentifier::OBJECT_NAME, None),
    )
    .await
    {
        Ok(Ok(ack)) => ack,
        Ok(Err(e)) => {
            report.error = Some(format!("ReadProperty Device Object_Name: {e:#}"));
            return finish(report_path.as_deref(), report);
        }
        Err(_) => {
            report.error = Some("object-name step timed out".into());
            return finish(report_path.as_deref(), report);
        }
    };
    let (name_val, _) = match decode_application_value(&name_ack.property_value, 0) {
        Ok(v) => v,
        Err(e) => {
            report.error = Some(format!("decode Object_Name: {e:#}"));
            return finish(report_path.as_deref(), report);
        }
    };
    let PropertyValue::CharacterString(name) = name_val else {
        report.error = Some(format!(
            "Object_Name expected CharacterString, got {name_val:?}"
        ));
        return finish(report_path.as_deref(), report);
    };
    info!("Device Object_Name = {name}");
    report.object_name = Some(name);

    let read_ai = || async {
        let ai_ack = timeout(
            Duration::from_secs(20),
            client.read_property(&mac, ai_oid, PropertyIdentifier::PRESENT_VALUE, None),
        )
        .await
        .context("AI PV step timed out")?
        .context("ReadProperty AI Present_Value")?;
        let (ai_val, _) = decode_application_value(&ai_ack.property_value, 0)?;
        Ok::<_, anyhow::Error>(ai_val)
    };

    let ai_val = match read_ai().await {
        Ok(v) => v,
        Err(e) => {
            report.error = Some(format!("{e:#}"));
            return finish(report_path.as_deref(), report);
        }
    };
    match ai_val {
        PropertyValue::Real(v) => {
            info!("AI:{} Present_Value = {v}", args.ai_instance);
            report.ai_present_value = Some(v);
        }
        other => {
            report.error = Some(format!("AI Present_Value expected Real, got {other:?}"));
            return finish(report_path.as_deref(), report);
        }
    }

    if args.loop_secs == 0 {
        info!("FEC diag PASS");
        report.ok = true;
        return finish(report_path.as_deref(), report);
    }

    info!(
        every_s = args.loop_secs,
        count = args.loop_count,
        "Peer loop starting — watch Workbench; Ctrl-C / SIGTERM to stop"
    );
    let mut n = 0u32;
    let mut ok = 0u32;
    let mut fail = 0u32;
    #[cfg(unix)]
    let mut sigterm = {
        use tokio::signal::unix::{signal, SignalKind};
        signal(SignalKind::terminate()).context("SIGTERM handler")?
    };
    loop {
        if args.loop_count > 0 && n >= args.loop_count {
            break;
        }
        tokio::select! {
            result = tokio::signal::ctrl_c() => {
                let _ = result;
                info!("SIGINT — finishing report");
                break;
            }
            () = async {
                #[cfg(unix)]
                {
                    sigterm.recv().await;
                }
                #[cfg(not(unix))]
                {
                    std::future::pending::<()>().await;
                }
            } => {
                info!("SIGTERM — finishing report");
                break;
            }
            () = sleep(Duration::from_secs(args.loop_secs)) => {
                n += 1;
                match read_ai().await {
                    Ok(PropertyValue::Real(v)) => {
                        ok += 1;
                        info!(n, ok, fail, "AI:{} PV={v}", args.ai_instance);
                        report.ai_present_value = Some(v);
                    }
                    Ok(other) => {
                        fail += 1;
                        error!(n, ok, fail, "AI PV expected Real, got {other:?}");
                    }
                    Err(e) => {
                        fail += 1;
                        error!(n, ok, fail, error = %e, "peer read failed");
                    }
                }
            }
        }
    }
    report.loop_ok = ok;
    report.loop_fail = fail;
    info!(ok, fail, "peer loop done");
    if fail > 0 {
        report.error = Some(format!("peer loop finished with {fail} failures ({ok} ok)"));
        return finish(report_path.as_deref(), report);
    }
    report.ok = true;
    finish(report_path.as_deref(), report)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn base_args() -> Args {
        Args {
            serial: "/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_BH001FQ0-if00-port0".into(),
            baud: 38400,
            mac: 3,
            max_master: 127,
            max_info_frames: 1,
            device_instance: 5007,
            expect_mac: 7,
            ai_instance: 1173,
            apdu_timeout_ms: 8000,
            settle_ms: 5000,
            loop_secs: 0,
            loop_count: 0,
            report: None,
        }
    }

    #[test]
    fn rejects_missing_distinct_mac() {
        let mut a = base_args();
        a.mac = 7;
        a.expect_mac = 7;
        assert!(validate_args(&a).is_err());
    }

    #[test]
    fn rejects_bad_baud() {
        let mut a = base_args();
        a.baud = 9601;
        assert!(validate_args(&a).is_err());
    }

    #[test]
    fn accepts_mac3_expect7() {
        assert!(validate_args(&base_args()).is_ok());
    }
}
