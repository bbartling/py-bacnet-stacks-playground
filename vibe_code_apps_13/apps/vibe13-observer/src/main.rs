//! Read-only local HTTP observer — NEVER opens a serial tty.
//! Publishes bounded JSON from a state directory written by other processes.

use std::net::SocketAddr;
use std::path::PathBuf;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use anyhow::{Context, Result};
use clap::Parser;
use serde_json::{json, Value};
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::TcpListener;
use tracing::{info, warn};

#[derive(Parser, Debug)]
#[command(
    name = "vibe13-observer",
    about = "Loopback HTTP observer (no tty ownership)"
)]
struct Args {
    #[arg(long, default_value = "127.0.0.1:8765")]
    bind: String,
    #[arg(long, default_value = ".")]
    state_dir: PathBuf,
}

fn now_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0)
}

fn load_status(state_dir: &PathBuf) -> Value {
    let path = state_dir.join("status.json");
    match std::fs::read_to_string(&path) {
        Ok(s) => serde_json::from_str(&s).unwrap_or_else(|_| {
            json!({
                "ok": false,
                "error": "status.json parse failed",
                "freshness": "stale",
                "observed_utc_ms": now_ms(),
            })
        }),
        Err(_) => json!({
            "ok": true,
            "freshness": "offline",
            "note": "waiting for status.json from mini/probe IPC",
            "tty_owner": false,
            "observed_utc_ms": now_ms(),
        }),
    }
}

async fn handle_client(mut socket: tokio::net::TcpStream, state_dir: PathBuf) -> Result<()> {
    let mut buf = [0u8; 1024];
    let _n = socket.read(&mut buf).await.unwrap_or(0);
    let body = serde_json::to_vec_pretty(&load_status(&state_dir))?;
    let resp = format!(
        "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
        body.len()
    );
    socket.write_all(resp.as_bytes()).await?;
    socket.write_all(&body).await?;
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
    std::fs::create_dir_all(&args.state_dir).ok();
    let addr: SocketAddr = args.bind.parse().context("parse --bind")?;
    if !addr.ip().is_loopback() {
        anyhow::bail!("observer bind must be loopback only (got {})", args.bind);
    }
    let listener = TcpListener::bind(addr).await.context("bind observer")?;
    info!(%addr, state = %args.state_dir.display(), "vibe13-observer listening (no tty)");

    loop {
        match listener.accept().await {
            Ok((sock, peer)) => {
                let dir = args.state_dir.clone();
                tokio::spawn(async move {
                    if let Err(e) = handle_client(sock, dir).await {
                        warn!(error = %e, %peer, "observer client error");
                    }
                });
            }
            Err(e) => {
                warn!(error = %e, "accept failed");
                tokio::time::sleep(Duration::from_millis(200)).await;
            }
        }
    }
}
