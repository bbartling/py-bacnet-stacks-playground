//! Receive-only MS/TP frame sniffer (no token participation / no TX).
//! Uses streaming decode from bacnet-transport (path-patch to USB fix for local proof).

use std::fs;
use std::io::ErrorKind;
use std::path::PathBuf;
use std::time::{Duration, Instant};

use anyhow::{bail, Context, Result};
use bacnet_transport::mstp_frame::{decode_frame_stream, FrameType, StreamDecode, PREAMBLE};
use clap::Parser;
use lab_common::BaudRate;
use serde::Serialize;
use tokio::io::AsyncReadExt;
use tokio::time::timeout;
use tokio_serial::{DataBits, FlowControl, Parity, SerialPortBuilderExt, StopBits};
use tracing::{info, warn};

#[derive(Parser, Debug)]
#[command(
    name = "mstp-passive-sniff",
    about = "RX-only MS/TP decode (no master TX)"
)]
struct Args {
    #[arg(long)]
    serial: String,
    #[arg(long, default_value_t = 38400)]
    baud: u32,
    #[arg(long, default_value_t = 30)]
    seconds: u64,
    #[arg(long)]
    report: Option<PathBuf>,
}

#[derive(Default, Serialize)]
struct SniffReport {
    ok: bool,
    serial: String,
    baud: u32,
    seconds: u64,
    rx_bytes: u64,
    complete_frames: u64,
    tokens: u64,
    poll_for_master: u64,
    data_frames: u64,
    invalid: u64,
    need_more_stalls: u64,
    sources_seen: Vec<u8>,
    error: Option<String>,
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
    let baud = BaudRate::try_from(args.baud).map_err(anyhow::Error::msg)?;
    if args.serial.trim().is_empty() {
        bail!("--serial required");
    }

    let mut report = SniffReport {
        serial: args.serial.clone(),
        baud: baud.as_u32(),
        seconds: args.seconds,
        ..Default::default()
    };

    info!(
        serial = %args.serial,
        baud = baud.as_u32(),
        seconds = args.seconds,
        "Passive sniff starting (no TX; 8N1, no flow control)"
    );

    let mut port = tokio_serial::new(&args.serial, baud.as_u32())
        .data_bits(DataBits::Eight)
        .parity(Parity::None)
        .stop_bits(StopBits::One)
        .flow_control(FlowControl::None)
        .timeout(Duration::from_millis(50))
        .open_native_async()
        .context("open serial")?;

    let deadline = Instant::now() + Duration::from_secs(args.seconds);
    let mut frame_buf: Vec<u8> = Vec::with_capacity(2048);
    let mut recv = vec![0u8; 2048];
    let mut sources = std::collections::BTreeSet::new();

    while Instant::now() < deadline {
        let remaining = deadline.saturating_duration_since(Instant::now());
        if remaining.is_zero() {
            break;
        }
        match timeout(remaining, port.read(&mut recv)).await {
            Err(_) => break,
            Ok(Ok(0)) => continue,
            Ok(Ok(n)) => {
                report.rx_bytes += n as u64;
                frame_buf.extend_from_slice(&recv[..n]);
                loop {
                    match decode_frame_stream(&frame_buf) {
                        StreamDecode::NeedMore => {
                            report.need_more_stalls += 1;
                            break;
                        }
                        StreamDecode::Complete { frame, consumed } => {
                            report.complete_frames += 1;
                            sources.insert(frame.source);
                            match frame.frame_type {
                                FrameType::Token => report.tokens += 1,
                                FrameType::PollForMaster => report.poll_for_master += 1,
                                FrameType::BACnetDataExpectingReply
                                | FrameType::BACnetDataNotExpectingReply => {
                                    report.data_frames += 1;
                                }
                                _ => {}
                            }
                            frame_buf.drain(..consumed);
                        }
                        StreamDecode::Invalid { discard } => {
                            report.invalid += 1;
                            let d = discard.max(1).min(frame_buf.len());
                            frame_buf.drain(..d);
                        }
                    }
                }
                if frame_buf.len() == 1 && frame_buf[0] == PREAMBLE[0] {
                    // keep lone 0x55
                } else if frame_buf.len() > 4096 {
                    warn!("buffer large; trimming");
                    frame_buf.clear();
                }
            }
            Ok(Err(e)) if e.kind() == ErrorKind::TimedOut => continue,
            Ok(Err(e)) => {
                report.error = Some(e.to_string());
                break;
            }
        }
    }

    report.sources_seen = sources.into_iter().collect();
    report.ok = report.rx_bytes > 0
        && report.complete_frames > 0
        && report.tokens > 0
        && report.error.is_none();

    info!(
        rx_bytes = report.rx_bytes,
        complete = report.complete_frames,
        tokens = report.tokens,
        pfm = report.poll_for_master,
        data = report.data_frames,
        invalid = report.invalid,
        sources = ?report.sources_seen,
        ok = report.ok,
        "Passive sniff done"
    );

    if let Some(path) = &args.report {
        if let Some(parent) = path.parent() {
            if !parent.as_os_str().is_empty() {
                fs::create_dir_all(parent)?;
            }
        }
        fs::write(path, serde_json::to_string_pretty(&report)?)?;
        info!(path = %path.display(), "wrote report");
    }

    if report.ok {
        Ok(())
    } else {
        bail!(
            "passive gate FAIL (rx={} frames={} tokens={})",
            report.rx_bytes,
            report.complete_frames,
            report.tokens
        );
    }
}
