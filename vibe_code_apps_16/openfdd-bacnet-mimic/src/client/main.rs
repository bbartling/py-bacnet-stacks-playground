//! # BACnet client (probe) — **start here for the test client app**
//!
//! This is a **separate program** from the server. It uses a random UDP port,
//! talks to the server on **47808**, and runs two checks:
//!
//! 1. **Unicast read** — read `object-name` on device 599999
//! 2. **Who-Is** — broadcast discover (often 0 results from same host — see README)
//!
//! ## How to run
//!
//! Start the server first (`./scripts/run.sh`), then in another terminal:
//!
//! ```bash
//! ./scripts/probe.sh
//! # or
//! cargo run --release --bin bacnet-probe
//! ```
//!
//! ## Where the logic lives
//!
//! | File | What it does |
//! |------|----------------|
//! | `main.rs` (this file) | Parse CLI args, run probe, exit code |
//! | `app.rs` | BACnet client read + Who-Is |
//! | `../shared/config.rs` | `--bind`, `--device`, `--broadcast` flags |
//! | `../shared/network.rs` | Bench IP / broadcast helpers |

mod app;

use clap::Parser;
use openfdd_bacnet_mimic::shared::config::ProbeArgs;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = ProbeArgs::parse();
    let result = app::run(args).await?;
    if !result.whois_ok() {
        std::process::exit(1);
    }
    Ok(())
}
