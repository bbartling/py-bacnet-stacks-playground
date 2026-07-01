//! Run the BACnet/IP server until Ctrl+C.

use std::sync::Arc;

use bacnet_server::server::BACnetServer;
use tokio::sync::Mutex;
use tracing::info;

use crate::config::{ServerArgs, OPENFDD_VENDOR_ID};
use crate::database::build_database;
use crate::network::{free_udp_port, nic_from_env, resolve_network, verify_udp_bind};

pub fn init_logging(debug: bool) {
    let filter = if debug {
        "debug,openfdd_bacnet_mimic=debug,bacnet_server=debug,bacnet_transport=debug"
    } else {
        "info,openfdd_bacnet_mimic=info,bacnet_server=info,bacnet_transport=warn"
    };
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new(filter)),
        )
        .init();
}

pub async fn run(args: ServerArgs) -> Result<(), Box<dyn std::error::Error>> {
    let nic = nic_from_env();
    let net = resolve_network(args.address, args.broadcast, &nic);

    info!(
        "device {} \"{}\" on UDP :{} (Who-Is → I-Am; no periodic I-Am)",
        args.instance, args.name, args.port
    );
    info!(
        "host_ip={} broadcast={} bind={}",
        net.device_ip, net.broadcast, net.bind_ip
    );

    if args.replace_existing {
        free_udp_port(args.port);
    }
    verify_udp_bind(net.bind_ip, args.port);

    let db = build_database(args.instance, &args.name)?;
    info!("object database: {} BACnet objects", db.len());

    let server = BACnetServer::bip_builder()
        .interface(net.bind_ip)
        .port(args.port)
        .broadcast_address(net.broadcast)
        .vendor_id(OPENFDD_VENDOR_ID)
        .database(db)
        .build()
        .await?;

    let server = Arc::new(Mutex::new(server));
    let mac = {
        let guard = server.lock().await;
        guard.local_mac().to_vec()
    };
    info!(
        "server MAC {:02x}:{:02x}:{:02x}:{:02x}:{:02x}:{:02x}",
        mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]
    );

    info!("listening — press Ctrl+C to stop");
    tokio::signal::ctrl_c().await?;
    let _ = server.lock().await.stop().await;
    info!("stopped");
    Ok(())
}
