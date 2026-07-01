//! # BACnet server — **start here for the server app**
//!
//! This program owns UDP port **47808** and pretends to be Open-FDD device **599999**.
//! When a BMS sends **Who-Is**, we answer with **I-Am** (no periodic broadcasts).
//!
//! ## How to run
//!
//! ```bash
//! ./scripts/run.sh
//! # or
//! cargo run --release --bin openfdd-bacnet-mimic
//! ```
//!
//! ## Where the logic lives
//!
//! | File | What it does |
//! |------|----------------|
//! | `main.rs` (this file) | Parse CLI args, start the server |
//! | `app.rs` | Build database, bind UDP, run until Ctrl+C |
//! | `../shared/config.rs` | Defaults (device id, port, vendor) |
//! | `../shared/network.rs` | Find bench IP, broadcast address |
//! | `../shared/database.rs` | BACnet AV/BV objects (Open-FDD points) |

mod app;

use clap::Parser;
use openfdd_bacnet_mimic::shared::config::ServerArgs;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = ServerArgs::parse();
    app::init_logging(args.debug);
    app::run(args).await
}
