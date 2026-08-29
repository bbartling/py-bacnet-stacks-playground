//! One-shot or 1 Hz MS/TP peer diag against a real field device (e.g. JCI FEC).
//! Not the Phase 2 mini-device acceptance profile.

use std::time::Duration;

use anyhow::{bail, Context, Result};
use bacnet_client::client::BACnetClient;
use bacnet_encoding::primitives::decode_application_value;
use bacnet_types::enums::{ObjectType, PropertyIdentifier};
use bacnet_types::primitives::{ObjectIdentifier, PropertyValue};
use clap::Parser;
use lab_common::BaudRate;
use mstp_lab::{master_config, open_mstp_transport};
use tokio::time::{sleep, timeout};
use tracing::{error, info, warn};

#[derive(Parser, Debug)]
#[command(name = "mstp-fec-diag", about = "Who-Is + ReadProperty on one USB MS/TP adapter")]
struct Args {
    #[arg(long)]
    serial: String,
    #[arg(long, default_value_t = 38400)]
    baud: u32,
    #[arg(long, default_value_t = 0)]
    mac: u8,
    #[arg(long, default_value_t = 127)]
    max_master: u8,
    #[arg(long, default_value_t = 1)]
    max_info_frames: u8,
    #[arg(long, default_value_t = 5007)]
    device_instance: u32,
    #[arg(long, default_value_t = 7)]
    expect_mac: u8,
    #[arg(long, default_value_t = 1173)]
    ai_instance: u32,
    #[arg(long, default_value_t = 8_000)]
    apdu_timeout_ms: u64,
    #[arg(long, default_value_t = 5_000)]
    settle_ms: u64,
    /// If > 0, keep reading Present_Value every N seconds (peer soak for Workbench watch).
    #[arg(long, default_value_t = 0)]
    loop_secs: u64,
    /// Stop after this many loop reads (0 = until Ctrl-C / SIGTERM).
    #[arg(long, default_value_t = 0)]
    loop_count: u32,
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
    let baud = BaudRate::try_from(args.baud).map_err(anyhow::Error::msg)?;
    let cfg = master_config(
        &args.serial,
        args.mac,
        baud,
        args.max_master,
        args.max_info_frames,
    );
    info!(
        serial = %args.serial,
        baud = baud.as_u32(),
        mac = args.mac,
        max_master = args.max_master,
        target_instance = args.device_instance,
        expect_mac = args.expect_mac,
        loop_secs = args.loop_secs,
        "Opening MS/TP probe (auto RS-485 direction)"
    );

    let endpoint = open_mstp_transport(&cfg)?;
    let client = BACnetClient::generic_builder()
        .transport(endpoint.transport)
        .apdu_timeout_ms(args.apdu_timeout_ms)
        .build()
        .await
        .context("start BACnet client")?;

    sleep(Duration::from_millis(args.settle_ms)).await;
    info!("Who-Is for instance {}", args.device_instance);
    client
        .who_is(Some(args.device_instance), Some(args.device_instance))
        .await
        .context("Who-Is")?;
    sleep(Duration::from_millis(2_000)).await;

    let Some(dev) = client.get_device(args.device_instance).await else {
        bail!(
            "no I-Am for instance {} after Who-Is (token/join or wiring?)",
            args.device_instance
        );
    };
    let got_mac = dev.mac_address.as_slice();
    info!(
        instance = args.device_instance,
        mac = ?got_mac,
        vendor_id = dev.vendor_id,
        "I-Am observed"
    );
    if got_mac != [args.expect_mac].as_slice() {
        warn!(
            expected = args.expect_mac,
            got = ?got_mac,
            "MAC differs from expect_mac (continuing reads anyway)"
        );
    }

    let mac = got_mac.to_vec();
    let device_oid =
        ObjectIdentifier::new(ObjectType::DEVICE, args.device_instance).context("device oid")?;
    let ai_oid =
        ObjectIdentifier::new(ObjectType::ANALOG_INPUT, args.ai_instance).context("ai oid")?;

    let name_ack = timeout(
        Duration::from_secs(30),
        client.read_property(&mac, device_oid, PropertyIdentifier::OBJECT_NAME, None),
    )
    .await
    .context("object-name step timed out")?
    .context("ReadProperty Device Object_Name")?;
    let (name_val, _) = decode_application_value(&name_ack.property_value, 0)?;
    info!("Device Object_Name = {name_val:?}");

    let read_ai = || async {
        let ai_ack = timeout(
            Duration::from_secs(20),
            client.read_property(&mac, ai_oid, PropertyIdentifier::PRESENT_VALUE, None),
        )
        .await
        .context("AI PV step timed out")?
        .context("ReadProperty AI Present_Value")?;
        let (ai_val, _) = decode_application_value(&ai_ack.property_value, 0)?;
        Ok::<_, anyhow::Error>(ai_val)
    };

    let ai_val = read_ai().await?;
    match ai_val {
        PropertyValue::Real(v) => info!("AI:{} Present_Value = {v}", args.ai_instance),
        other => info!("AI:{} Present_Value = {other:?}", args.ai_instance),
    }

    if args.loop_secs == 0 {
        info!("FEC diag PASS");
        return Ok(());
    }

    info!(
        every_s = args.loop_secs,
        count = args.loop_count,
        "Peer loop starting — watch Workbench; Ctrl-C / SIGTERM to stop"
    );
    let mut n = 0u32;
    let mut ok = 0u32;
    let mut fail = 0u32;
    loop {
        if args.loop_count > 0 && n >= args.loop_count {
            break;
        }
        sleep(Duration::from_secs(args.loop_secs)).await;
        n += 1;
        match read_ai().await {
            Ok(PropertyValue::Real(v)) => {
                ok += 1;
                info!(n, ok, fail, "AI:{} PV={v}", args.ai_instance);
            }
            Ok(other) => {
                ok += 1;
                info!(n, ok, fail, "AI:{} PV={other:?}", args.ai_instance);
            }
            Err(e) => {
                fail += 1;
                error!(n, ok, fail, error = %e, "peer read failed");
            }
        }
    }
    info!(ok, fail, "peer loop done");
    if fail > 0 {
        bail!("peer loop finished with {fail} failures ({ok} ok)");
    }
    Ok(())
}
