//! Binary entry point: `cargo run --release` or `./scripts/run.sh`

use clap::Parser;
use openfdd_bacnet_mimic::config::ServerArgs;
use openfdd_bacnet_mimic::server;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = ServerArgs::parse();
    server::init_logging(args.debug);
    server::run(args).await
}
