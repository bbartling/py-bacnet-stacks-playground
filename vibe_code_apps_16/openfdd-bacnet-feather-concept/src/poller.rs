//! Multi-device field poller — VOLTTRON platform.driver–inspired scheduler.
//!
//! Each configured device is a "driver" with its own scrape interval and phase
//! offset. The scheduler:
//!   1. wakes every `tick_ms`
//!   2. selects overdue devices (most overdue first)
//!   3. scrapes at most `max_concurrent` devices in parallel
//!   4. appends that device's rows to Feather (one publish per device scrape)
//!
//! Routed MSTP devices use `read_property_routed`; BIP devices use plain
//! `read_property`. Mini-device alone owns UDP 47808.

use std::path::Path;
use std::sync::Arc;
use std::time::{Duration, Instant};

use anyhow::{Context, Result};
use bacnet_client::client::BACnetClient;
use bacnet_encoding::primitives::decode_application_value;
use bacnet_transport::bip::BipTransport;
use bacnet_transport::bvll::encode_bip_mac;
use bacnet_types::enums::{ObjectType, PropertyIdentifier};
use bacnet_types::primitives::{ObjectIdentifier, PropertyValue};
use chrono::Utc;
use tokio::sync::Mutex;
use tracing::{info, warn};

use crate::app_config::{AppConfig, DeviceConfig, DevicePointConfig};
use crate::feather_store::{append_samples, read_samples_from_feather, SampleRow};
use crate::latest::AppStateHandle;
use crate::network::{resolve_poller_bind, subnet_broadcast};

#[derive(Debug)]
struct DeviceRuntime {
    cfg: DeviceConfig,
    interval: Duration,
    /// Next time this device is eligible to scrape.
    next_due: Instant,
    last_ok: Option<Instant>,
    consecutive_failures: u32,
    total_scrapes: u64,
    total_ok: u64,
}

pub async fn run_poller_forever(cfg: AppConfig, state: AppStateHandle) -> Result<()> {
    let store_path = cfg.feather_store_path();
    if let Some(parent) = store_path.parent() {
        std::fs::create_dir_all(parent)
            .with_context(|| format!("creating store {}", parent.display()))?;
    }
    // Never wipe on restart — keep growing the same telemetry.feather.
    if store_path.is_file() {
        match read_samples_from_feather(&store_path) {
            Ok(existing) => info!(
                "feather store {} already has {} row(s) — will append (not recreate)",
                store_path.display(),
                existing.len()
            ),
            Err(err) => warn!(
                "feather store {} exists but is unreadable ({err:#}) — new rows will start a fresh file",
                store_path.display()
            ),
        }
    } else {
        info!(
            "feather store {} not found yet — will create on first scrape",
            store_path.display()
        );
    }

    let nic = cfg.server.nic.clone();
    let bind = resolve_poller_bind(cfg.poller.bind, cfg.server.address, &nic);
    let broadcast = cfg
        .poller
        .broadcast
        .or(cfg.server.broadcast)
        .unwrap_or_else(|| subnet_broadcast(bind));

    let devices: Vec<DeviceConfig> = cfg
        .poller
        .devices
        .iter()
        .filter(|d| d.enabled && !d.points.is_empty())
        .cloned()
        .collect();

    if devices.is_empty() {
        anyhow::bail!("no enabled poller.devices with points — check config");
    }

    let tick = Duration::from_millis(cfg.poller.tick_ms.max(50));
    let max_concurrent = cfg.poller.max_concurrent.max(1);
    let default_interval = cfg.poller.interval_secs.max(1);
    let clone_from = cfg.server.clone_from_point.clone();

    info!(
        "poller bind={bind}:0 (ephemeral) broadcast={broadcast} tick={}ms max_concurrent={max_concurrent} devices={}",
        tick.as_millis(),
        devices.len()
    );

    let started = Instant::now();
    let mut runtimes: Vec<DeviceRuntime> = devices
        .into_iter()
        .map(|d| {
            let interval = Duration::from_secs(d.interval_or(default_interval));
            let offset = Duration::from_secs(d.offset_secs);
            let route = if d.is_routed() {
                format!(
                    "routed net={} mac={:?}",
                    d.mstp_network.unwrap_or(0),
                    d.mstp_mac.as_deref().unwrap_or(&[])
                )
            } else {
                "bip-direct".into()
            };
            info!(
                "device \"{}\" id={} @ {}:{} interval={}s offset={}s critical={} points={} ({route})",
                d.name,
                d.device_instance,
                d.host,
                d.port,
                interval.as_secs(),
                d.offset_secs,
                d.critical,
                d.points.iter().filter(|p| p.enabled).count(),
            );
            DeviceRuntime {
                cfg: d,
                interval,
                next_due: started + offset,
                last_ok: None,
                consecutive_failures: 0,
                total_scrapes: 0,
                total_ok: 0,
            }
        })
        .collect();

    let client = Arc::new(
        BACnetClient::bip_builder()
            .interface(bind)
            .port(0)
            .broadcast_address(broadcast)
            .apdu_timeout_ms(8000)
            .build()
            .await
            .context("BACnetClient::build")?,
    );

    // Serialize Feather appends (atomic rewrite is not concurrent-safe).
    let feather_lock = Arc::new(Mutex::new(()));

    loop {
        let now = Instant::now();

        // Most overdue first (VOLTTRON-style: don't starve slow devices).
        let mut due_idx: Vec<usize> = runtimes
            .iter()
            .enumerate()
            .filter(|(_, r)| now >= r.next_due)
            .map(|(i, _)| i)
            .collect();
        due_idx.sort_by_key(|&i| runtimes[i].next_due);

        let batch: Vec<usize> = due_idx.into_iter().take(max_concurrent).collect();

        if !batch.is_empty() {
            let mut handles = Vec::with_capacity(batch.len());
            for idx in batch {
                let device = runtimes[idx].cfg.clone();
                let client = Arc::clone(&client);
                let store_path = store_path.clone();
                let feather_lock = Arc::clone(&feather_lock);
                let clone_from = clone_from.clone();
                handles.push(tokio::spawn(async move {
                    scrape_device(&client, &device, &store_path, &feather_lock, &clone_from).await
                }));
                // Reserve slot: push next_due forward so we don't double-schedule
                // while the scrape is in flight.
                runtimes[idx].next_due = now + runtimes[idx].interval;
                runtimes[idx].total_scrapes += 1;
            }

            let mut results = Vec::with_capacity(handles.len());
            for handle in handles {
                match handle.await {
                    Ok(r) => results.push(r),
                    Err(err) => warn!("scrape task join failed: {err}"),
                }
            }

            apply_scrape_results(&mut runtimes, &results, &state, &clone_from).await;
        }

        // Stale critical devices → APP-FAULT even if no scrape ran this tick.
        refresh_fault_from_runtimes(&runtimes, &state, &clone_from).await;

        tokio::time::sleep(tick).await;
    }
}

struct ScrapeResult {
    device_name: String,
    ok: bool,
    duct_t: Option<f64>,
    reason: String,
}

async fn scrape_device(
    client: &BACnetClient<BipTransport>,
    device: &DeviceConfig,
    store_path: &Path,
    feather_lock: &Mutex<()>,
    clone_from: &str,
) -> ScrapeResult {
    let started = Instant::now();
    let points: Vec<&DevicePointConfig> = device.points.iter().filter(|p| p.enabled).collect();
    let mut rows = Vec::with_capacity(points.len());
    let mut failures = Vec::new();
    let mut duct_t = None;

    info!(
        "scrape start \"{}\" id={} ({} points)",
        device.name,
        device.device_instance,
        points.len()
    );

    for point in &points {
        match read_one_point(client, device, point).await {
            Ok(row) => {
                info!(
                    "  {} \"{}\" {}:{} {}={:.2} {}",
                    device.name,
                    row.point_name,
                    row.object_type,
                    row.object_instance,
                    row.point_name,
                    row.present_value,
                    row.units
                );
                if device.critical && row.point_name.eq_ignore_ascii_case(clone_from) {
                    duct_t = Some(row.present_value);
                }
                rows.push(row);
            }
            Err(err) => {
                let msg = format!(
                    "{}.{} {}:{} — {err:#}",
                    device.name, point.point_name, point.object_type, point.object_instance
                );
                warn!("  read failed {msg}");
                failures.push(msg);
            }
        }
    }

    let mut feather_err = None;
    if !rows.is_empty() {
        let _guard = feather_lock.lock().await;
        match append_samples(store_path, &rows) {
            Ok(_path) => info!(
                "scrape ok \"{}\" +{} row(s) ({:.0}ms)",
                device.name,
                rows.len(),
                started.elapsed().as_millis()
            ),
            Err(err) => {
                let msg = format!("feather append failed: {err:#}");
                warn!("{msg}");
                feather_err = Some(msg);
            }
        }
    } else {
        feather_err = Some(format!("no points read on \"{}\"", device.name));
    }

    let expected = points.len();
    let ok = failures.is_empty()
        && feather_err.is_none()
        && rows.len() == expected
        && (!device.critical || duct_t.is_some());

    let reason = if ok {
        "ok".into()
    } else {
        let mut parts = failures.clone();
        if device.critical && duct_t.is_none() {
            parts.push(format!("missing clone source \"{clone_from}\""));
        }
        if let Some(fe) = &feather_err {
            parts.push(fe.clone());
        }
        if parts.is_empty() {
            parts.push("incomplete scrape".into());
        }
        parts.join("; ")
    };

    ScrapeResult {
        device_name: device.name.clone(),
        ok,
        duct_t,
        reason,
    }
}

async fn apply_scrape_results(
    runtimes: &mut [DeviceRuntime],
    results: &[ScrapeResult],
    state: &AppStateHandle,
    _clone_from: &str,
) {
    for result in results {
        if let Some(rt) = runtimes
            .iter_mut()
            .find(|r| r.cfg.name == result.device_name)
        {
            if result.ok {
                rt.last_ok = Some(Instant::now());
                rt.consecutive_failures = 0;
                rt.total_ok += 1;
            } else {
                rt.consecutive_failures += 1;
                warn!(
                    "device \"{}\" scrape failed (#{}) — {}",
                    result.device_name, rt.consecutive_failures, result.reason
                );
            }
        }

        if let Some(v) = result.duct_t {
            let mut s = state.write().await;
            s.duct_t = Some(v);
        }
    }
}

async fn refresh_fault_from_runtimes(
    runtimes: &[DeviceRuntime],
    state: &AppStateHandle,
    clone_from: &str,
) {
    let mut reasons = Vec::new();
    let mut any_critical = false;
    let mut all_critical_ok = true;

    for rt in runtimes {
        if !rt.cfg.critical {
            continue;
        }
        any_critical = true;
        let stale_after = rt.interval * 3;
        let healthy = match rt.last_ok {
            Some(ok_at) if ok_at.elapsed() <= stale_after && rt.consecutive_failures == 0 => true,
            Some(ok_at) if ok_at.elapsed() > stale_after => {
                reasons.push(format!(
                    "\"{}\" stale ({}s since ok)",
                    rt.cfg.name,
                    ok_at.elapsed().as_secs()
                ));
                false
            }
            Some(_) => {
                reasons.push(format!(
                    "\"{}\" failing ({} consecutive)",
                    rt.cfg.name, rt.consecutive_failures
                ));
                false
            }
            None => {
                reasons.push(format!("\"{}\" waiting for first ok scrape", rt.cfg.name));
                false
            }
        };
        if !healthy {
            all_critical_ok = false;
        }
    }

    let mut s = state.write().await;
    if !any_critical {
        // No critical device configured — fault if we never got duct_t.
        if s.duct_t.is_none() {
            s.fault = true;
            s.fault_reason = format!("no critical device; missing \"{clone_from}\"");
        }
        return;
    }

    if all_critical_ok && s.duct_t.is_some() {
        s.fault = false;
        s.fault_reason = "ok".into();
        s.last_ok_at = Some(Instant::now());
    } else {
        s.fault = true;
        if s.duct_t.is_none() {
            reasons.push(format!("missing clone source \"{clone_from}\""));
        }
        s.fault_reason = if reasons.is_empty() {
            "critical device unhealthy".into()
        } else {
            reasons.join("; ")
        };
    }
}

async fn read_one_point(
    client: &BACnetClient<BipTransport>,
    device: &DeviceConfig,
    point: &DevicePointConfig,
) -> Result<SampleRow> {
    let object_type = parse_object_type(&point.object_type)?;
    let oid = ObjectIdentifier::new(object_type, point.object_instance)?;
    let mac = encode_bip_mac(device.host.octets(), device.port);

    let value = if device.is_routed() {
        let mstp_net = device.mstp_network.unwrap_or(0);
        let mstp_mac = device.mstp_mac.clone().unwrap_or_default();
        let ack = client
            .read_property_routed(
                &mac,
                mstp_net,
                &mstp_mac,
                oid,
                PropertyIdentifier::PRESENT_VALUE,
                None,
            )
            .await
            .with_context(|| {
                format!(
                    "ReadProperty routed {} via {}:{} net={mstp_net} mac={mstp_mac:?}",
                    device.name, device.host, device.port
                )
            })?;
        decode_present_value(&ack.property_value)?
    } else {
        let ack = client
            .read_property(&mac, oid, PropertyIdentifier::PRESENT_VALUE, None)
            .await
            .with_context(|| {
                format!(
                    "ReadProperty BIP {} @ {}:{}",
                    device.name, device.host, device.port
                )
            })?;
        decode_present_value(&ack.property_value)?
    };

    Ok(SampleRow {
        ts_utc: Utc::now(),
        device_name: device.name.clone(),
        device_instance: device.device_instance,
        object_type: point.object_type.to_ascii_lowercase(),
        object_instance: point.object_instance,
        point_name: point.point_name.clone(),
        present_value: value,
        units: point.units.clone(),
    })
}

fn parse_object_type(s: &str) -> Result<ObjectType> {
    match s.to_ascii_lowercase().replace('-', "_").as_str() {
        "analog_input" | "ai" => Ok(ObjectType::ANALOG_INPUT),
        "analog_value" | "av" => Ok(ObjectType::ANALOG_VALUE),
        "analog_output" | "ao" => Ok(ObjectType::ANALOG_OUTPUT),
        "binary_input" | "bi" => Ok(ObjectType::BINARY_INPUT),
        "binary_value" | "bv" => Ok(ObjectType::BINARY_VALUE),
        "binary_output" | "bo" => Ok(ObjectType::BINARY_OUTPUT),
        "multi_state_value" | "msv" => Ok(ObjectType::MULTI_STATE_VALUE),
        "multi_state_input" | "msi" => Ok(ObjectType::MULTI_STATE_INPUT),
        "multi_state_output" | "mso" => Ok(ObjectType::MULTI_STATE_OUTPUT),
        other => anyhow::bail!("unsupported object_type '{other}'"),
    }
}

fn decode_present_value(bytes: &[u8]) -> Result<f64> {
    let (val, _) = decode_application_value(bytes, 0).context("decode_application_value")?;
    match val {
        PropertyValue::Real(v) => Ok(v as f64),
        PropertyValue::Double(v) => Ok(v),
        PropertyValue::Unsigned(v) => Ok(v as f64),
        PropertyValue::Signed(v) => Ok(v as f64),
        PropertyValue::Enumerated(v) => Ok(v as f64),
        PropertyValue::Boolean(v) => Ok(if v { 1.0 } else { 0.0 }),
        other => anyhow::bail!("unexpected property value {other:?}"),
    }
}
