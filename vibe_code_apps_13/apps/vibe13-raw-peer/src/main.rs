//! Two-host raw RS-485 peer (non-BACnet). Each process owns ONE adapter.
//! Private envelope: magic + seq + len + payload + CRC16-CCITT.

use std::time::Duration;

use anyhow::{Context, Result};
use clap::Parser;
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio_serial::SerialPortBuilderExt;
use tracing::{info, warn};

const MAGIC: [u8; 2] = [0x56, 0x13]; // Vibe13

#[derive(Parser, Debug)]
#[command(
    name = "vibe13-raw-peer",
    about = "Half-duplex raw RS-485 peer (no BACnet)"
)]
struct Args {
    #[arg(long)]
    serial: String,
    #[arg(long, default_value_t = 38400)]
    baud: u32,
    #[arg(long, default_value = "server")]
    role: String,
    #[arg(long, default_value_t = 100)]
    exchanges: u32,
    #[arg(long, default_value_t = 200)]
    interval_ms: u64,
    #[arg(long, default_value_t = 1000)]
    timeout_ms: u64,
}

fn crc16_ccitt(data: &[u8]) -> u16 {
    let mut crc: u16 = 0xFFFF;
    for b in data {
        crc ^= u16::from(*b) << 8;
        for _ in 0..8 {
            if crc & 0x8000 != 0 {
                crc = (crc << 1) ^ 0x1021;
            } else {
                crc <<= 1;
            }
        }
    }
    crc
}

fn encode(seq: u32, payload: &[u8]) -> Vec<u8> {
    let mut body = Vec::with_capacity(2 + 4 + 2 + payload.len() + 2);
    body.extend_from_slice(&MAGIC);
    body.extend_from_slice(&seq.to_be_bytes());
    body.extend_from_slice(&(payload.len() as u16).to_be_bytes());
    body.extend_from_slice(payload);
    let crc = crc16_ccitt(&body);
    body.extend_from_slice(&crc.to_be_bytes());
    body
}

fn decode(frame: &[u8]) -> Result<(u32, Vec<u8>)> {
    anyhow::ensure!(frame.len() >= 10, "frame too short");
    anyhow::ensure!(frame[0..2] == MAGIC, "bad magic");
    let seq = u32::from_be_bytes(frame[2..6].try_into()?);
    let len = u16::from_be_bytes(frame[6..8].try_into()?) as usize;
    anyhow::ensure!(frame.len() == 8 + len + 2, "length mismatch");
    let payload = frame[8..8 + len].to_vec();
    let want = u16::from_be_bytes(frame[8 + len..].try_into()?);
    let got = crc16_ccitt(&frame[..8 + len]);
    anyhow::ensure!(want == got, "crc mismatch");
    Ok((seq, payload))
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
    let role = args.role.to_ascii_lowercase();
    anyhow::ensure!(
        role == "server" || role == "probe" || role == "initiator" || role == "responder",
        "role must be server/probe (or initiator/responder)"
    );
    let initiator = role == "probe" || role == "initiator";

    let mut port = tokio_serial::new(&args.serial, args.baud)
        .timeout(Duration::from_millis(args.timeout_ms))
        .open_native_async()
        .with_context(|| format!("open {}", args.serial))?;

    info!(
        serial = %args.serial,
        baud = args.baud,
        role = %role,
        exchanges = args.exchanges,
        "raw peer starting (non-BACnet)"
    );

    let mut ok = 0u32;
    let mut fail = 0u32;
    for seq in 1..=args.exchanges {
        if initiator {
            let payload = format!("ping-{seq}").into_bytes();
            let frame = encode(seq, &payload);
            port.write_all(&frame).await?;
            port.flush().await?;
            let mut buf = vec![0u8; 256];
            match tokio::time::timeout(Duration::from_millis(args.timeout_ms), port.read(&mut buf))
                .await
            {
                Ok(Ok(n)) if n > 0 => match decode(&buf[..n]) {
                    Ok((rseq, rp)) if rseq == seq && rp.starts_with(b"pong-") => ok += 1,
                    Ok(_) => {
                        fail += 1;
                        warn!(seq, "unexpected reply");
                    }
                    Err(e) => {
                        fail += 1;
                        warn!(seq, error = %e, "decode fail");
                    }
                },
                _ => {
                    fail += 1;
                    warn!(seq, "timeout waiting reply");
                }
            }
            tokio::time::sleep(Duration::from_millis(args.interval_ms)).await;
        } else {
            let mut buf = vec![0u8; 256];
            match tokio::time::timeout(
                Duration::from_millis(args.timeout_ms.saturating_mul(5)),
                port.read(&mut buf),
            )
            .await
            {
                Ok(Ok(n)) if n > 0 => match decode(&buf[..n]) {
                    Ok((rseq, rp)) => {
                        let reply = encode(
                            rseq,
                            &format!("pong-{}", String::from_utf8_lossy(&rp)).into_bytes(),
                        );
                        // turnaround gap for half-duplex
                        tokio::time::sleep(Duration::from_millis(20)).await;
                        port.write_all(&reply).await?;
                        port.flush().await?;
                        ok += 1;
                    }
                    Err(e) => {
                        fail += 1;
                        warn!(error = %e, "bad request");
                    }
                },
                _ => {
                    // idle wait; continue until exchanges filled by initiator side
                    if !initiator {
                        continue;
                    }
                }
            }
            if ok + fail >= args.exchanges {
                break;
            }
        }
    }

    info!(ok, fail, "raw peer finished");
    if fail > 0 {
        anyhow::bail!("raw peer failures={fail}");
    }
    Ok(())
}
