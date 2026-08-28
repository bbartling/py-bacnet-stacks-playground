//! MS/TP acceptance sequences (loopback + hardware).

use std::time::{Duration, Instant};

use anyhow::{Context, Result};
use bacnet_client::client::BACnetClient;
use bacnet_encoding::primitives::{decode_application_value, encode_property_value};
use bacnet_server::server::BACnetServer;
use bacnet_transport::mstp::{LoopbackSerial, MstpConfig, MstpTransport, SerialPort};
use bacnet_types::enums::{ObjectType, PropertyIdentifier};
use bacnet_types::primitives::{ObjectIdentifier, PropertyValue};
use bytes::BytesMut;
use tokio::time::sleep;

use crate::database::{build_mini_device_database, MiniDeviceConfig, VENDOR_ID};
use crate::report::AcceptanceReport;
use crate::transport::{default_master_config, open_mstp_transport};

const DEFAULT_DEVICE_INSTANCE: u32 = 123_001;
const TOKEN_SETTLE_MS: u64 = 3500;

#[derive(Debug, Clone)]
pub struct AcceptanceOptions {
    pub device_instance: u32,
    pub probe_mac: u8,
    pub device_mac: u8,
    pub baud: u32,
    pub repeated_reads: u32,
}

impl Default for AcceptanceOptions {
    fn default() -> Self {
        Self {
            device_instance: DEFAULT_DEVICE_INSTANCE,
            probe_mac: 0,
            device_mac: 1,
            baud: 38_400,
            repeated_reads: 10,
        }
    }
}

async fn start_device<S: SerialPort + 'static>(
    serial: S,
    opts: &AcceptanceOptions,
) -> Result<BACnetServer<MstpTransport<S>>> {
    let db = build_mini_device_database(&MiniDeviceConfig {
        instance: opts.device_instance,
        name: "Rust MS/TP Mini Device".to_owned(),
    })?;
    let mstp_cfg = MstpConfig {
        this_station: opts.device_mac,
        max_master: 10,
        max_info_frames: 1,
        baud_rate: opts.baud,
    };
    let transport = MstpTransport::new(serial, mstp_cfg);
    BACnetServer::generic_builder()
        .transport(transport)
        .database(db)
        .vendor_id(VENDOR_ID)
        .build()
        .await
        .context("start mini-device server")
}

async fn start_probe<S: SerialPort + 'static>(
    serial: S,
    opts: &AcceptanceOptions,
) -> Result<BACnetClient<MstpTransport<S>>> {
    let mstp_cfg = MstpConfig {
        this_station: opts.probe_mac,
        max_master: 10,
        max_info_frames: 1,
        baud_rate: opts.baud,
    };
    let transport = MstpTransport::new(serial, mstp_cfg);
    BACnetClient::generic_builder()
        .transport(transport)
        .build()
        .await
        .context("start mstp probe client")
}

fn device_mac(opts: &AcceptanceOptions) -> Vec<u8> {
    vec![opts.device_mac]
}

async fn timed_step<F, Fut>(report: &mut AcceptanceReport, name: &str, fut: F)
where
    F: FnOnce() -> Fut,
    Fut: std::future::Future<Output = Result<String>>,
{
    let start = Instant::now();
    match fut().await {
        Ok(detail) => report.push_step(
            name,
            true,
            detail,
            Some(start.elapsed().as_secs_f64() * 1000.0),
        ),
        Err(e) => report.push_step(
            name,
            false,
            e.to_string(),
            Some(start.elapsed().as_secs_f64() * 1000.0),
        ),
    }
}

async fn run_acceptance_core<S: SerialPort + 'static>(
    mut client: BACnetClient<MstpTransport<S>>,
    opts: AcceptanceOptions,
    mode: &str,
) -> AcceptanceReport {
    let mut report = AcceptanceReport::new(
        mode,
        opts.device_instance,
        opts.probe_mac,
        opts.device_mac,
        opts.baud,
    );

    sleep(Duration::from_millis(TOKEN_SETTLE_MS)).await;
    timed_step(&mut report, "token_stabilize", || async {
        Ok(format!("waited {TOKEN_SETTLE_MS} ms for MS/TP token"))
    })
    .await;

    let mac = device_mac(&opts);
    let device_oid =
        ObjectIdentifier::new(ObjectType::DEVICE, opts.device_instance).expect("device oid");
    let ai_oid = ObjectIdentifier::new(ObjectType::ANALOG_INPUT, 1).expect("ai oid");
    let av_oid = ObjectIdentifier::new(ObjectType::ANALOG_VALUE, 2).expect("av oid");

    timed_step(&mut report, "who_is", || async {
        client
            .who_is(Some(opts.device_instance), Some(opts.device_instance))
            .await?;
        sleep(Duration::from_millis(800)).await;
        let n = client.discovered_devices().await.len();
        Ok(format!("Who-Is sent; {n} device(s) in table"))
    })
    .await;

    timed_step(&mut report, "read_device_object_name", || async {
        let ack = client
            .read_property(&mac, device_oid, PropertyIdentifier::OBJECT_NAME, None)
            .await?;
        let (val, _) =
            decode_application_value(&ack.property_value, 0).context("decode object-name")?;
        let name = match val {
            PropertyValue::CharacterString(s) => s,
            other => anyhow::bail!("expected CharacterString, got {other:?}"),
        };
        Ok(format!("Object_Name={name:?}"))
    })
    .await;

    timed_step(&mut report, "read_ai_present_value", || async {
        let ack = client
            .read_property(&mac, ai_oid, PropertyIdentifier::PRESENT_VALUE, None)
            .await?;
        let (val, _) = decode_application_value(&ack.property_value, 0).context("decode AI PV")?;
        Ok(format!("AI:1 Present_Value={val:?}"))
    })
    .await;

    timed_step(&mut report, "write_av_priority_8", || async {
        let mut buf = BytesMut::new();
        encode_property_value(&mut buf, &PropertyValue::Real(75.0))?;
        client
            .write_property(
                &mac,
                av_oid,
                PropertyIdentifier::PRESENT_VALUE,
                None,
                buf.to_vec(),
                Some(8),
            )
            .await?;
        Ok("AV:2 commanded to 75.0 @ priority 8".to_owned())
    })
    .await;

    timed_step(&mut report, "read_av_after_write", || async {
        let ack = client
            .read_property(&mac, av_oid, PropertyIdentifier::PRESENT_VALUE, None)
            .await?;
        let (val, _) = decode_application_value(&ack.property_value, 0).context("decode AV PV")?;
        let v = match val {
            PropertyValue::Real(n) => n,
            other => anyhow::bail!("expected Real, got {other:?}"),
        };
        if (v - 75.0).abs() > 0.01 {
            anyhow::bail!("expected 75.0, got {v}");
        }
        Ok(format!("AV:2 Present_Value={v}"))
    })
    .await;

    timed_step(&mut report, "relinquish_av_priority_8", || async {
        let mut buf = BytesMut::new();
        encode_property_value(&mut buf, &PropertyValue::Null)?;
        client
            .write_property(
                &mac,
                av_oid,
                PropertyIdentifier::PRESENT_VALUE,
                None,
                buf.to_vec(),
                Some(8),
            )
            .await?;
        Ok("AV:2 priority 8 relinquished (NULL)".to_owned())
    })
    .await;

    timed_step(&mut report, "repeated_reads", || async {
        let mut latencies = Vec::new();
        for _ in 0..opts.repeated_reads {
            let t0 = Instant::now();
            let _ = client
                .read_property(&mac, ai_oid, PropertyIdentifier::PRESENT_VALUE, None)
                .await?;
            latencies.push(t0.elapsed().as_secs_f64() * 1000.0);
        }
        let mean = latencies.iter().sum::<f64>() / latencies.len() as f64;
        Ok(format!(
            "{} reads OK, mean {:.1} ms",
            opts.repeated_reads, mean
        ))
    })
    .await;

    let _ = client.stop().await;
    report.finalize();
    report
}

/// CI-safe loopback acceptance (no USB hardware).
pub async fn run_loopback_acceptance(opts: AcceptanceOptions) -> AcceptanceReport {
    let (probe_serial, device_serial) = LoopbackSerial::pair();
    let mut server = match start_device(device_serial, &opts).await {
        Ok(s) => s,
        Err(e) => {
            let mut report = AcceptanceReport::new(
                "loopback",
                opts.device_instance,
                opts.probe_mac,
                opts.device_mac,
                opts.baud,
            );
            report.push_step("start_device", false, e.to_string(), None);
            report.finalize();
            return report;
        }
    };

    let client = match start_probe(probe_serial, &opts).await {
        Ok(c) => c,
        Err(e) => {
            let mut report = AcceptanceReport::new(
                "loopback",
                opts.device_instance,
                opts.probe_mac,
                opts.device_mac,
                opts.baud,
            );
            report.push_step("start_probe", false, e.to_string(), None);
            report.finalize();
            let _ = server.stop().await;
            return report;
        }
    };

    let report = run_acceptance_core(client, opts, "loopback").await;
    let _ = server.stop().await;
    report
}

/// Hardware acceptance: probe only (run `mstp-mini-device` on `--device-serial` first).
pub async fn run_hardware_acceptance(
    probe_serial: &str,
    opts: AcceptanceOptions,
) -> AcceptanceReport {
    let mut report = AcceptanceReport::new(
        "hardware",
        opts.device_instance,
        opts.probe_mac,
        opts.device_mac,
        opts.baud,
    );

    let probe_master = match default_master_config(probe_serial, opts.probe_mac).validate() {
        Ok(()) => default_master_config(probe_serial, opts.probe_mac),
        Err(e) => {
            report.push_step("validate_probe_port", false, e.to_string(), None);
            report.finalize();
            return report;
        }
    };

    let probe_endpoint = match open_mstp_transport(&probe_master) {
        Ok(e) => e,
        Err(e) => {
            report.push_step("open_probe_port", false, e.to_string(), None);
            report.finalize();
            return report;
        }
    };

    let client = match BACnetClient::generic_builder()
        .transport(probe_endpoint.transport)
        .build()
        .await
    {
        Ok(c) => c,
        Err(e) => {
            report.push_step("start_probe", false, e.to_string(), None);
            report.finalize();
            return report;
        }
    };

    run_acceptance_core(client, opts, "hardware").await
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn loopback_acceptance_passes() {
        let report = run_loopback_acceptance(AcceptanceOptions {
            repeated_reads: 5,
            ..Default::default()
        })
        .await;
        assert_eq!(report.status, "Passed", "{report:?}");
    }
}
