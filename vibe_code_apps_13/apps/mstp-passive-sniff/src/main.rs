//! Receive-only MS/TP frame sniffer (no token participation / no TX).
//! Streaming decode from bacnet-transport @ Clause 9 CRC + USB reassembly pin.

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

/// rusty-bacnet pin recorded into hardware reports (must match workspace Cargo.toml).
const RUSTY_BACNET_REV: &str = "73a1fd41df7df2dfb3fa005cf339f347751f0286";

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
    rusty_bacnet_rev: String,
    rx_bytes: u64,
    complete_frames: u64,
    tokens: u64,
    token_0_from_7: u64,
    poll_for_master: u64,
    data_frames: u64,
    invalid: u64,
    need_more_stalls: u64,
    valid_ratio: f64,
    sources_seen: Vec<u8>,
    error: Option<String>,
}

#[tokio::main]
#[allow(clippy::too_many_lines)]
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
        rusty_bacnet_rev: RUSTY_BACNET_REV.to_string(),
        ..Default::default()
    };

    info!(
        serial = %args.serial,
        baud = baud.as_u32(),
        seconds = args.seconds,
        rusty = RUSTY_BACNET_REV,
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
            Ok(Ok(0)) => {}
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
                            if frame.frame_type == FrameType::Token
                                && frame.destination == 0
                                && frame.source == 7
                            {
                                report.token_0_from_7 += 1;
                            }
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
            Ok(Err(e)) if e.kind() == ErrorKind::TimedOut => {}
            Ok(Err(e)) => {
                report.error = Some(e.to_string());
                break;
            }
        }
    }

    report.sources_seen = sources.into_iter().collect();
    let denom = report.complete_frames + report.invalid;
    report.valid_ratio = if denom == 0 {
        0.0
    } else {
        #[allow(clippy::cast_precision_loss)]
        {
            report.complete_frames as f64 / denom as f64
        }
    };
    report.ok = report.rx_bytes > 0
        && report.complete_frames > 0
        && report.tokens > 0
        && report.sources_seen.contains(&0)
        && report.sources_seen.contains(&7)
        && report.token_0_from_7 > 0
        && report.error.is_none();

    info!(
        rx_bytes = report.rx_bytes,
        complete = report.complete_frames,
        tokens = report.tokens,
        token_0_from_7 = report.token_0_from_7,
        pfm = report.poll_for_master,
        data = report.data_frames,
        invalid = report.invalid,
        valid_ratio = report.valid_ratio,
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
            "passive gate FAIL (rx={} frames={} tokens={} token_0_from_7={} sources={:?})",
            report.rx_bytes,
            report.complete_frames,
            report.tokens,
            report.token_0_from_7,
            report.sources_seen
        );
    }
}

#[cfg(test)]
mod offline_fixture_tests {
    use bacnet_transport::mstp_frame::{
        decode_frame, decode_frame_stream, encode_frame, FrameType, StreamDecode,
    };
    use bytes::BytesMut;

    /// Live trunk Token: dest BASRT(0) ← FEC(7), header CRC 0x37.
    const TOKEN_0_FROM_7: &[u8] = &[0x55, 0xFF, 0x00, 0x00, 0x07, 0x00, 0x00, 0x37];

    #[test]
    fn offline_literal_token_0_from_7_decodes() {
        let (frame, consumed) = decode_frame(TOKEN_0_FROM_7).expect("Token 0<-7");
        assert_eq!(consumed, 8);
        assert_eq!(frame.frame_type, FrameType::Token);
        assert_eq!(frame.destination, 0);
        assert_eq!(frame.source, 7);

        let mut enc = BytesMut::new();
        encode_frame(&mut enc, &frame).unwrap();
        assert_eq!(&enc[..], TOKEN_0_FROM_7);
    }

    #[test]
    fn offline_stream_split_across_usb_chunks() {
        let wire = TOKEN_0_FROM_7;
        let mut buf = Vec::new();
        for chunk in [2usize, 3, 1, 2] {
            let start = buf.len();
            let end = (start + chunk).min(wire.len());
            if start >= wire.len() {
                break;
            }
            buf.extend_from_slice(&wire[start..end]);
            match decode_frame_stream(&buf) {
                StreamDecode::NeedMore => {}
                StreamDecode::Complete { frame, consumed } => {
                    assert_eq!(frame.source, 7);
                    assert_eq!(consumed, 8);
                    return;
                }
                StreamDecode::Invalid { .. } => panic!("unexpected invalid"),
            }
        }
        match decode_frame_stream(&buf) {
            StreamDecode::Complete { frame, .. } => {
                assert_eq!(frame.frame_type, FrameType::Token);
                assert_eq!(frame.destination, 0);
                assert_eq!(frame.source, 7);
            }
            other => panic!("expected complete, got {other:?}"),
        }
    }
}
