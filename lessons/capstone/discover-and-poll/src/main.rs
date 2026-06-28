//! Day 46 capstone — BACnet discovery + poll skeleton.
//!
//! Replace UDP placeholders with [rusty-bacnet](https://github.com/jscott3201/rusty-bacnet)
//! after Day 41. See ../README.md.

mod discover;
mod poll;

use anyhow::Result;
use clap::{Parser, Subcommand};

#[derive(Parser)]
#[command(name = "discover-and-poll", about = "Day 46 BACnet commission tool (capstone skeleton)")]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    /// Send Who-Is (UDP placeholder) and print discovered devices
    Discover {
        #[arg(long, default_value = "0.0.0.0:47808")]
        bind: String,
        #[arg(long)]
        device: Option<u32>,
    },
    /// Poll present-values and write CSV (stub rows until rusty-bacnet wired)
    Poll {
        #[arg(long, default_value = "5007")]
        device: u32,
        #[arg(long, default_value = "192.168.204.200")]
        host: String,
        #[arg(long, default_value = "commission_snapshot.csv")]
        out: String,
        #[arg(long, default_value = "analogInput:1")]
        objects: Vec<String>,
    },
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Command::Discover { bind, device } => discover::run(&bind, device)?,
        Command::Poll {
            device,
            host,
            out,
            objects,
        } => poll::run(device, &host, &out, &objects)?,
    }
    Ok(())
}
