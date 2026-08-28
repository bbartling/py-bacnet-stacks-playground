//! Phase 1 dual USB RS-485 wire test — private envelopes only (no `BACnet`).

use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};

use anyhow::{anyhow, bail, Context, Result};
use clap::Parser;
use lab_common::{
    atomic_write_json, deadline_ms, encode_envelope, resolve_same_device, BaudRate, Direction,
    Envelope, EnvelopeParser, FailureRecord, LatencyStats, ParseEvent, PayloadPattern,
    ReportStatus, WireReport, BOUNDARY_LENGTHS,
};
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::sync::mpsc;
use tokio_serial::{SerialPortBuilderExt, SerialStream};
use tracing::{error, info, warn};

#[derive(Debug, Parser)]
#[command(name = "serial-wire-test", about = "Phase 1 dual USB RS-485 wire test")]
struct Cli {
    /// Prefer /dev/serial/by-id/...
    #[arg(long)]
    port_a: PathBuf,
    #[arg(long)]
    port_b: PathBuf,
    /// One of: 9600, 19200, 38400, 57600, 76800, 115200
    #[arg(long, default_value_t = 38400)]
    baud: u32,
    #[arg(long, default_value_t = 100)]
    rounds: u32,
    #[arg(long, default_value_t = 256)]
    max_payload: u16,
    #[arg(long, default_value_t = 1337)]
    seed: u64,
    /// Override calculated per-exchange deadline (ms).
    #[arg(long)]
    timeout_ms: Option<u64>,
    #[arg(long, default_value_t = 5)]
    turnaround_guard_ms: u64,
    #[arg(long)]
    report: PathBuf,
    #[arg(long, default_value = "info")]
    log: String,
}

#[derive(Debug, Clone, Copy)]
enum PortId {
    A,
    B,
}

#[derive(Debug)]
enum ReaderMsg {
    Frame { port: PortId, envelope: Envelope },
    Rejected { detail: String },
    SerialError { detail: String },
    Eof,
}

#[tokio::main]
async fn main() {
    let code = match run().await {
        Ok(0) => 0,
        Ok(c) => c,
        Err(err) => {
            eprintln!("error: {err:#}");
            2
        }
    };
    std::process::exit(code);
}

#[allow(clippy::too_many_lines)]
async fn run() -> Result<i32> {
    let cli = Cli::parse();
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new(&cli.log)),
        )
        .init();

    let baud = BaudRate::try_from(cli.baud).map_err(|e| anyhow!("{e}"))?;
    if cli.rounds == 0 || cli.rounds > 1_000_000 {
        bail!("rounds must be 1..=1000000");
    }
    if cli.max_payload > 256 {
        bail!("max-payload hard limit is 256");
    }
    let (resolved_a, resolved_b) =
        resolve_same_device(&cli.port_a, &cli.port_b).map_err(|e| anyhow!("{e}"))?;

    let max_env = 10 + usize::from(cli.max_payload) + 4;
    let timeout_ms = cli.timeout_ms.unwrap_or_else(|| deadline_ms(baud, max_env));

    info!(
        port_a = %cli.port_a.display(),
        port_b = %cli.port_b.display(),
        resolved_a = %resolved_a.display(),
        resolved_b = %resolved_b.display(),
        baud = baud.as_u32(),
        rounds = cli.rounds,
        max_payload = cli.max_payload,
        seed = cli.seed,
        timeout_ms,
        turnaround_guard_ms = cli.turnaround_guard_ms,
        report = %cli.report.display(),
        "serial-wire-test starting (8N1, no flow control, auto direction)"
    );

    let stop = Arc::new(AtomicBool::new(false));
    {
        let stop = Arc::clone(&stop);
        tokio::spawn(async move {
            let _ = tokio::signal::ctrl_c().await;
            warn!("SIGINT — finishing current exchange and writing report");
            stop.store(true, Ordering::SeqCst);
        });
    }

    let started = Instant::now();
    let started_utc = chrono::Utc::now().to_rfc3339();

    let mut report = WireReport {
        schema_version: "phase1_wire_v1".into(),
        status: ReportStatus::Failed,
        reason: String::new(),
        started_utc,
        ended_utc: String::new(),
        elapsed_ms: 0,
        port_a: cli.port_a.display().to_string(),
        port_b: cli.port_b.display().to_string(),
        port_a_resolved: resolved_a.display().to_string(),
        port_b_resolved: resolved_b.display().to_string(),
        baud: baud.as_u32(),
        rounds_requested: cli.rounds,
        rounds_completed: 0,
        seed: cli.seed,
        max_payload: cli.max_payload,
        timeout_ms,
        turnaround_guard_ms: cli.turnaround_guard_ms,
        envelopes_ok_a_to_b: 0,
        envelopes_ok_b_to_a: 0,
        payload_bytes_a_to_b: 0,
        payload_bytes_b_to_a: 0,
        local_echo_a: 0,
        local_echo_b: 0,
        missing: 0,
        corrupt: 0,
        duplicate: 0,
        stale: 0,
        unexpected: 0,
        parser_rejected: 0,
        serial_errors: 0,
        latency_ms_a_to_b: LatencyStats::default(),
        latency_ms_b_to_a: LatencyStats::default(),
        failures: Vec::new(),
        os: std::env::consts::OS.into(),
        arch: std::env::consts::ARCH.into(),
    };

    let mut port_a = open_port(&cli.port_a, baud)
        .with_context(|| format!("open port-a {}", cli.port_a.display()))?;
    let mut port_b = match open_port(&cli.port_b, baud) {
        Ok(p) => p,
        Err(e) => {
            drop(port_a);
            return Err(e).with_context(|| format!("open port-b {}", cli.port_b.display()));
        }
    };

    drain_stale(&mut port_a, PortId::A).await?;
    drain_stale(&mut port_b, PortId::B).await?;

    // Split into readers (owned half) — use full duplex streams with separate tasks via clone of fd?
    // tokio-serial SerialStream is not split easily on all platforms; use one coordinator with
    // try_read via two tasks by splitting into read/write halves.
    let (a_reader, mut a_writer) = tokio::io::split(port_a);
    let (b_reader, mut b_writer) = tokio::io::split(port_b);

    let (tx, mut rx) = mpsc::channel::<ReaderMsg>(64);
    let max_payload = cli.max_payload;
    let stop_r = Arc::clone(&stop);
    let tx_a = tx.clone();
    tokio::spawn(reader_task(a_reader, PortId::A, max_payload, tx_a, stop_r));
    let stop_r = Arc::clone(&stop);
    tokio::spawn(reader_task(b_reader, PortId::B, max_payload, tx, stop_r));

    let mut sequence: u32 = 0;
    let mut lengths = BOUNDARY_LENGTHS
        .into_iter()
        .filter(|&l| l <= cli.max_payload)
        .collect::<Vec<_>>();
    if lengths.is_empty() {
        lengths.push(0);
    }
    let patterns = PayloadPattern::CYCLE;
    let mut length_i = 0usize;
    let mut pattern_i = 0usize;
    let mut payload_buf = vec![0_u8; usize::from(cli.max_payload)];
    let mut encode_buf = Vec::with_capacity(max_env);
    let guard = Duration::from_millis(cli.turnaround_guard_ms);
    let timeout = Duration::from_millis(timeout_ms);

    let mut exit_code = 0i32;

    for round in 1..=cli.rounds {
        if stop.load(Ordering::SeqCst) {
            report.status = ReportStatus::Interrupted;
            report.reason = "interrupted by signal".into();
            exit_code = 130;
            break;
        }

        let len = lengths[length_i % lengths.len()];
        length_i = length_i.wrapping_add(1);
        let pattern = patterns[pattern_i % patterns.len()];
        pattern_i = pattern_i.wrapping_add(1);
        let payload = &mut payload_buf[..usize::from(len)];
        pattern.fill(payload, cli.seed, sequence);

        // A -> B
        sequence = sequence.wrapping_add(1);
        let seq_ab = sequence;
        encode_envelope(Direction::AToB, seq_ab, payload, &mut encode_buf)?;
        let t0 = Instant::now();
        a_writer
            .write_all(&encode_buf)
            .await
            .context("write A->B")?;
        a_writer.flush().await.context("flush A")?;

        match wait_peer(
            &mut rx,
            Direction::AToB,
            seq_ab,
            payload,
            PortId::B,
            PortId::A,
            timeout,
            &mut report,
        )
        .await
        {
            Ok(_latency) => {
                report.envelopes_ok_a_to_b += 1;
                report.payload_bytes_a_to_b += u64::from(len);
                report
                    .latency_ms_a_to_b
                    .push(t0.elapsed().as_secs_f64() * 1000.0);
            }
            Err(kind) => {
                push_fail(&mut report, round, Direction::AToB, seq_ab, &kind);
                report.status = ReportStatus::Failed;
                report.reason = kind;
                exit_code = 1;
                report.rounds_completed = round - 1;
                break;
            }
        }

        tokio::time::sleep(guard).await;

        // B -> A
        sequence = sequence.wrapping_add(1);
        let seq_ba = sequence;
        encode_envelope(Direction::BToA, seq_ba, payload, &mut encode_buf)?;
        let t1 = Instant::now();
        b_writer
            .write_all(&encode_buf)
            .await
            .context("write B->A")?;
        b_writer.flush().await.context("flush B")?;

        match wait_peer(
            &mut rx,
            Direction::BToA,
            seq_ba,
            payload,
            PortId::A,
            PortId::B,
            timeout,
            &mut report,
        )
        .await
        {
            Ok(latency) => {
                report.envelopes_ok_b_to_a += 1;
                report.payload_bytes_b_to_a += u64::from(len);
                report
                    .latency_ms_b_to_a
                    .push(t1.elapsed().as_secs_f64() * 1000.0);
                let _ = latency;
            }
            Err(kind) => {
                push_fail(&mut report, round, Direction::BToA, seq_ba, &kind);
                report.status = ReportStatus::Failed;
                report.reason = kind;
                exit_code = 1;
                report.rounds_completed = round - 1;
                break;
            }
        }

        report.rounds_completed = round;
        if round % 500 == 0 || round == cli.rounds {
            info!(round, "progress");
        }
        tokio::time::sleep(guard).await;
    }

    if exit_code == 0 && report.status != ReportStatus::Interrupted {
        report.status = ReportStatus::Passed;
        report.reason = "all peer frames ok".into();
    }

    stop.store(true, Ordering::SeqCst);
    report.ended_utc = chrono::Utc::now().to_rfc3339();
    report.elapsed_ms = u64::try_from(started.elapsed().as_millis()).unwrap_or(u64::MAX);
    atomic_write_json(&cli.report, &report).context("write report")?;
    info!(
        status = ?report.status,
        rounds = report.rounds_completed,
        path = %cli.report.display(),
        "report written"
    );

    if report.status == ReportStatus::Passed {
        Ok(0)
    } else if exit_code != 0 {
        Ok(exit_code)
    } else {
        Ok(1)
    }
}

fn push_fail(report: &mut WireReport, round: u32, dir: Direction, seq: u32, kind: &str) {
    if report.failures.len() < 32 {
        report.failures.push(FailureRecord {
            round,
            direction: dir.to_string(),
            sequence: seq,
            kind: kind.to_owned(),
            detail: kind.to_owned(),
        });
    }
    if kind.contains("missing") || kind.contains("timeout") {
        report.missing += 1;
    } else if kind.contains("corrupt") || kind.contains("CRC") || kind.contains("payload") {
        report.corrupt += 1;
    } else if kind.contains("duplicate") {
        report.duplicate += 1;
    } else if kind.contains("stale") {
        report.stale += 1;
    } else if kind.contains("unexpected") {
        report.unexpected += 1;
    }
}

#[allow(clippy::too_many_arguments)]
async fn wait_peer(
    rx: &mut mpsc::Receiver<ReaderMsg>,
    expect_dir: Direction,
    expect_seq: u32,
    expect_payload: &[u8],
    peer: PortId,
    local: PortId,
    timeout: Duration,
    report: &mut WireReport,
) -> Result<f64, String> {
    let deadline = tokio::time::Instant::now() + timeout;
    let t0 = Instant::now();
    loop {
        let left = deadline.saturating_duration_since(tokio::time::Instant::now());
        if left.is_zero() {
            return Err(format!(
                "timeout waiting for {expect_dir} seq={expect_seq} on peer"
            ));
        }
        match tokio::time::timeout(left, rx.recv()).await {
            Ok(Some(ReaderMsg::Frame { port, envelope })) => {
                let is_peer = matches!(
                    (&port, &peer),
                    (PortId::A, PortId::A) | (PortId::B, PortId::B)
                );
                let is_local = matches!(
                    (&port, &local),
                    (PortId::A, PortId::A) | (PortId::B, PortId::B)
                );
                if is_local
                    && envelope.direction == expect_dir
                    && envelope.sequence == expect_seq
                    && envelope.payload == expect_payload
                {
                    match port {
                        PortId::A => report.local_echo_a += 1,
                        PortId::B => report.local_echo_b += 1,
                    }
                    continue;
                }
                if is_peer {
                    if envelope.sequence < expect_seq {
                        report.stale += 1;
                        continue;
                    }
                    if envelope.sequence == expect_seq && envelope.direction == expect_dir {
                        if envelope.payload == expect_payload {
                            return Ok(t0.elapsed().as_secs_f64() * 1000.0);
                        }
                        return Err(format!("corrupt payload seq={expect_seq} dir={expect_dir}"));
                    }
                    if envelope.sequence == expect_seq {
                        return Err(format!(
                            "unexpected direction got={} want={expect_dir}",
                            envelope.direction
                        ));
                    }
                    report.unexpected += 1;
                    continue;
                }
                report.unexpected += 1;
            }
            Ok(Some(ReaderMsg::Rejected { detail })) => {
                report.parser_rejected += 1;
                return Err(format!("parser rejected: {detail}"));
            }
            Ok(Some(ReaderMsg::SerialError { detail })) => {
                report.serial_errors += 1;
                return Err(format!("serial error: {detail}"));
            }
            Ok(Some(ReaderMsg::Eof)) => {
                report.serial_errors += 1;
                return Err("peer serial EOF / unplug".into());
            }
            Ok(None) => return Err("reader channel closed".into()),
            Err(_) => {
                return Err(format!(
                    "timeout waiting for {expect_dir} seq={expect_seq} on peer"
                ));
            }
        }
    }
}

fn open_port(path: &Path, baud: BaudRate) -> Result<SerialStream> {
    let builder = tokio_serial::new(path.to_string_lossy(), baud.as_u32())
        .data_bits(tokio_serial::DataBits::Eight)
        .parity(tokio_serial::Parity::None)
        .stop_bits(tokio_serial::StopBits::One)
        .flow_control(tokio_serial::FlowControl::None);
    let stream = builder
        .open_native_async()
        .with_context(|| format!("open {}", path.display()))?;
    Ok(stream)
}

async fn drain_stale(port: &mut SerialStream, id: PortId) -> Result<()> {
    let mut buf = [0_u8; 512];
    let mut total = 0usize;
    let deadline = Instant::now() + Duration::from_millis(50);
    while Instant::now() < deadline {
        match tokio::time::timeout(Duration::from_millis(10), port.read(&mut buf)).await {
            Ok(Ok(0)) | Err(_) => break,
            Ok(Ok(n)) => total += n,
            Ok(Err(e)) if e.kind() == std::io::ErrorKind::TimedOut => break,
            Ok(Err(e)) if e.kind() == std::io::ErrorKind::WouldBlock => break,
            Ok(Err(e)) => {
                warn!(?id, error = %e, "drain read error");
                break;
            }
        }
    }
    if total > 0 {
        warn!(?id, bytes = total, "drained stale bytes before test");
    }
    Ok(())
}

async fn reader_task<R: AsyncReadExt + Unpin>(
    mut reader: R,
    port: PortId,
    max_payload: u16,
    tx: mpsc::Sender<ReaderMsg>,
    stop: Arc<AtomicBool>,
) {
    let mut parser = EnvelopeParser::new(max_payload);
    let mut buf = [0_u8; 512];
    while !stop.load(Ordering::SeqCst) {
        match reader.read(&mut buf).await {
            Ok(0) => {
                let _ = tx.send(ReaderMsg::Eof).await;
                break;
            }
            Ok(n) => {
                for ev in parser.push(&buf[..n]) {
                    let msg = match ev {
                        ParseEvent::Frame(envelope) => ReaderMsg::Frame { port, envelope },
                        ParseEvent::Rejected(err) => ReaderMsg::Rejected {
                            detail: err.to_string(),
                        },
                        ParseEvent::Resynced { .. } => continue,
                    };
                    if tx.send(msg).await.is_err() {
                        return;
                    }
                }
            }
            Err(e) => {
                error!(?port, error = %e, "serial read failed");
                let _ = tx
                    .send(ReaderMsg::SerialError {
                        detail: e.to_string(),
                    })
                    .await;
                break;
            }
        }
    }
}
