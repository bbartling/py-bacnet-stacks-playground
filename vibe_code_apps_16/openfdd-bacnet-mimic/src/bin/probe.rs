//! Binary entry point: `cargo run --release --bin bacnet-probe` or `./scripts/probe.sh`

use clap::Parser;
use openfdd_bacnet_mimic::config::ProbeArgs;
use openfdd_bacnet_mimic::probe;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = ProbeArgs::parse();
    let result = probe::run(args).await?;
    if !result.whois_ok() {
        std::process::exit(1);
    }
    Ok(())
}
