//! Two-host raw RS-485 peer (non-BACnet). Each process owns ONE adapter.
//! Private envelope: magic + seq + len + payload + CRC16-CCITT.
//! Serial is a byte stream — never assume one read() == one frame.

use std::time::{Duration, Instant};

use anyhow::{Context, Result};
use clap::Parser;
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio_serial::SerialPortBuilderExt;
use tracing::{info, warn};

const MAGIC: [u8; 2] = [0x56, 0x13]; // Vibe13
const MAX_PAYLOAD: usize = 1024;
const MAX_BUF: usize = 8 + MAX_PAYLOAD + 2 + 64;

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

#[derive(Debug, Default)]
struct FrameDecoder {
    buf: Vec<u8>,
    pub bad_magic: u64,
    pub bad_length: u64,
    pub bad_crc: u64,
    pub oversized: u64,
}

impl FrameDecoder {
    fn push(&mut self, chunk: &[u8]) {
        self.buf.extend_from_slice(chunk);
        if self.buf.len() > MAX_BUF {
            self.oversized += 1;
            let keep = MAX_BUF / 2;
            let drop_n = self.buf.len() - keep;
            self.buf.drain(..drop_n);
        }
    }

    /// Pull next complete frame if available.
    fn next_frame(&mut self) -> Option<(u32, Vec<u8>)> {
        loop {
            if self.buf.len() < 2 {
                return None;
            }
            // Resynchronize on magic.
            if let Some(pos) = self.buf.windows(2).position(|w| w == MAGIC) {
                if pos > 0 {
                    self.bad_magic += 1;
                    self.buf.drain(..pos);
                }
            } else {
                // Keep last byte in case magic straddles reads.
                let keep = self.buf.len().saturating_sub(1);
                if keep > 0 {
                    self.bad_magic += 1;
                    self.buf.drain(..keep);
                }
                return None;
            }
            if self.buf.len() < 8 {
                return None;
            }
            let len = u16::from_be_bytes([self.buf[6], self.buf[7]]) as usize;
            if len > MAX_PAYLOAD {
                self.bad_length += 1;
                self.buf.drain(..2); // skip this magic, resync
                continue;
            }
            let total = 8 + len + 2;
            if self.buf.len() < total {
                return None;
            }
            let frame = self.buf[..total].to_vec();
            self.buf.drain(..total);
            let want = u16::from_be_bytes([frame[total - 2], frame[total - 1]]);
            let got = crc16_ccitt(&frame[..total - 2]);
            if want != got {
                self.bad_crc += 1;
                continue;
            }
            let seq = u32::from_be_bytes(frame[2..6].try_into().ok()?);
            let payload = frame[8..8 + len].to_vec();
            return Some((seq, payload));
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

    let mut decoder = FrameDecoder::default();
    let mut ok = 0u32;
    let mut fail = 0u32;
    let deadline = Instant::now()
        + Duration::from_millis(args.timeout_ms.saturating_mul(args.exchanges as u64 + 5));

    for seq in 1..=args.exchanges {
        if Instant::now() > deadline {
            fail += 1;
            warn!(seq, "total deadline exceeded");
            break;
        }
        if initiator {
            let payload = format!("ping-{seq}").into_bytes();
            let frame = encode(seq, &payload);
            port.write_all(&frame).await?;
            port.flush().await?;
            let wait_until = Instant::now() + Duration::from_millis(args.timeout_ms);
            let mut got = false;
            while Instant::now() < wait_until {
                let mut chunk = [0u8; 256];
                match tokio::time::timeout(Duration::from_millis(50), port.read(&mut chunk)).await {
                    Ok(Ok(n)) if n > 0 => decoder.push(&chunk[..n]),
                    _ => {}
                }
                while let Some((rseq, rp)) = decoder.next_frame() {
                    if rseq == seq && rp.starts_with(b"pong-") {
                        ok += 1;
                        got = true;
                        break;
                    }
                    fail += 1;
                    warn!(seq, rseq, "unexpected reply");
                }
                if got {
                    break;
                }
                tokio::task::yield_now().await;
            }
            if !got {
                fail += 1;
                warn!(seq, "timeout waiting reply");
            }
            tokio::time::sleep(Duration::from_millis(args.interval_ms)).await;
        } else {
            let wait_until =
                Instant::now() + Duration::from_millis(args.timeout_ms.saturating_mul(5));
            let mut handled = false;
            while Instant::now() < wait_until {
                let mut chunk = [0u8; 256];
                match tokio::time::timeout(Duration::from_millis(50), port.read(&mut chunk)).await {
                    Ok(Ok(n)) if n > 0 => decoder.push(&chunk[..n]),
                    _ => {}
                }
                if let Some((rseq, rp)) = decoder.next_frame() {
                    let reply = encode(
                        rseq,
                        &format!("pong-{}", String::from_utf8_lossy(&rp)).into_bytes(),
                    );
                    tokio::time::sleep(Duration::from_millis(20)).await;
                    port.write_all(&reply).await?;
                    port.flush().await?;
                    ok += 1;
                    handled = true;
                    break;
                }
                tokio::task::yield_now().await;
            }
            if !handled {
                // idle; keep waiting for initiator exchanges
                continue;
            }
            if ok + fail >= args.exchanges {
                break;
            }
        }
    }

    info!(
        ok,
        fail,
        bad_magic = decoder.bad_magic,
        bad_length = decoder.bad_length,
        bad_crc = decoder.bad_crc,
        "raw peer finished"
    );
    if fail > 0 {
        anyhow::bail!("raw peer failures={fail}");
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn split_across_reads() {
        let frame = encode(7, b"hi");
        let mut d = FrameDecoder::default();
        d.push(&frame[..3]);
        assert!(d.next_frame().is_none());
        d.push(&frame[3..]);
        let (seq, p) = d.next_frame().unwrap();
        assert_eq!(seq, 7);
        assert_eq!(p, b"hi");
    }

    #[test]
    fn coalesced_two_frames() {
        let mut blob = encode(1, b"a");
        blob.extend_from_slice(&encode(2, b"b"));
        let mut d = FrameDecoder::default();
        d.push(&blob);
        assert_eq!(d.next_frame().unwrap().0, 1);
        assert_eq!(d.next_frame().unwrap().0, 2);
    }

    #[test]
    fn noise_before_magic() {
        let mut blob = vec![0x00, 0xff, 0x13];
        blob.extend_from_slice(&encode(3, b"x"));
        let mut d = FrameDecoder::default();
        d.push(&blob);
        assert_eq!(d.next_frame().unwrap().0, 3);
        assert!(d.bad_magic >= 1);
    }

    #[test]
    fn bad_crc_dropped() {
        let mut frame = encode(1, b"z");
        *frame.last_mut().unwrap() ^= 0xff;
        let mut d = FrameDecoder::default();
        d.push(&frame);
        assert!(d.next_frame().is_none());
        assert_eq!(d.bad_crc, 1);
    }

    #[test]
    fn bad_length_oversized() {
        let mut frame = encode(1, b"ok");
        frame[6] = 0xff;
        frame[7] = 0xff;
        let mut d = FrameDecoder::default();
        d.push(&frame);
        assert!(d.next_frame().is_none());
        assert!(d.bad_length >= 1);
    }

    #[test]
    fn truncation_waits() {
        let frame = encode(9, b"hello");
        let mut d = FrameDecoder::default();
        d.push(&frame[..frame.len() - 1]);
        assert!(d.next_frame().is_none());
        d.push(&frame[frame.len() - 1..]);
        assert_eq!(d.next_frame().unwrap().0, 9);
    }
}
