//! BACnet/IP mini-device — same stack pattern as `openfdd-bacnet-mimic`.
//!
//! Listens on UDP **47808** (0xBAC0), answers Who-Is with I-Am (no periodic spam).
//! Device instance **5000**:
//! - AV:1 `5007-duct-t-clone` — mirrors field DUCT-T
//! - BI:1 `APP-FAULT` — active (true) when poller/field reads are unhealthy

use std::sync::Arc;
use std::time::Duration;

use anyhow::{Context, Result};
use bacnet_objects::analog::AnalogValueObject;
use bacnet_objects::binary::BinaryInputObject;
use bacnet_objects::database::ObjectDatabase;
use bacnet_objects::device::{DeviceConfig, DeviceObject};
use bacnet_objects::traits::BACnetObject;
use bacnet_server::server::BACnetServer;
use bacnet_transport::bip::BipTransport;
use bacnet_types::enums::{ObjectType, PropertyIdentifier};
use bacnet_types::primitives::{ObjectIdentifier, PropertyValue};
use tokio::sync::{Mutex, RwLock};
use tracing::{info, warn};

use crate::app_config::{ServerConfig, TEMP_UNITS_DEGREES_F, VENDOR_ID};
use crate::latest::AppStateHandle;
use crate::network::{free_udp_port, resolve_network, verify_udp_bind};

/// Owns the BACnet/IP mini-device server.
pub struct MiniDeviceRuntime {
    server: Arc<Mutex<BACnetServer<BipTransport>>>,
}

impl MiniDeviceRuntime {
    /// Start mini-device (mimic-style) and mirror `state` into clone AV + APP-FAULT BI.
    pub async fn start(cfg: &ServerConfig, state: AppStateHandle) -> Result<Self> {
        let net = resolve_network(cfg.address, cfg.broadcast, &cfg.nic);

        info!(
            "device {} \"{}\" on UDP :{} (Who-Is → I-Am; no periodic I-Am)",
            cfg.instance, cfg.name, cfg.port
        );
        info!(
            "host_ip={} broadcast={} bind={}",
            net.device_ip, net.broadcast, net.bind_ip
        );
        info!(
            "clone point: analogValue:{} \"{}\" (mirrors field {} every {}s)",
            cfg.temp_object_instance,
            cfg.temp_point_name,
            cfg.clone_from_point,
            cfg.value_update_secs
        );
        info!(
            "status point: binaryInput:{} \"{}\" (active=FAULT)",
            cfg.status_object_instance, cfg.status_point_name
        );

        free_udp_port(cfg.port);
        verify_udp_bind(net.bind_ip, cfg.port).context("UDP bind check")?;

        let db = build_database(cfg)?;
        info!("object database: {} BACnet objects", db.len());

        let server = BACnetServer::bip_builder()
            .interface(net.bind_ip)
            .port(cfg.port)
            .broadcast_address(net.broadcast)
            .vendor_id(VENDOR_ID)
            .database(db)
            .build()
            .await
            .context("BACnetServer::build")?;

        let db_for_updates = Arc::clone(server.database());
        let mac = server.local_mac().to_vec();
        info!(
            "server MAC {:02x}:{:02x}:{:02x}:{:02x}:{:02x}:{:02x}",
            mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]
        );

        let server = Arc::new(Mutex::new(server));

        let update_secs = cfg.value_update_secs.max(1);
        tokio::spawn(mirror_state_to_points(
            db_for_updates,
            state,
            cfg.temp_object_instance,
            cfg.temp_point_name.clone(),
            cfg.status_object_instance,
            cfg.status_point_name.clone(),
            update_secs,
        ));

        info!(
            "listening — Workbench/YABE Who-Is should show device {}",
            cfg.instance
        );
        Ok(Self { server })
    }

    /// Force APP-FAULT active (e.g. poller task died) while the server stays up.
    pub async fn set_fault(state: &AppStateHandle, reason: impl Into<String>) {
        let mut s = state.write().await;
        s.fault = true;
        s.fault_reason = reason.into();
    }

    pub async fn shutdown(&mut self) {
        info!("stopping BACnet mini-device server");
        let _ = self.server.lock().await.stop().await;
    }
}

/// Build device + clone AV + APP-FAULT BI — object-list pattern matches openfdd-bacnet-mimic.
fn build_database(cfg: &ServerConfig) -> Result<ObjectDatabase> {
    let mut db = ObjectDatabase::new();
    let device_oid = ObjectIdentifier::new(ObjectType::DEVICE, cfg.instance)?;

    let mut clone_av = AnalogValueObject::new(
        cfg.temp_object_instance,
        &cfg.temp_point_name,
        TEMP_UNITS_DEGREES_F,
    )
    .context("AnalogValueObject::new")?;
    clone_av.set_description(
        "POC clone of field device 5007 analogInput:1192 (DUCT-T) — updated from poller",
    );
    clone_av.set_present_value(0.0);
    db.add(Box::new(clone_av)).context("add AV clone")?;

    let mut fault_bi = BinaryInputObject::new(cfg.status_object_instance, &cfg.status_point_name)
        .context("BinaryInputObject::new")?;
    fault_bi.set_description(
        "Application fault: active=true when field BACnet reads fail, data is stale, or poller crashed",
    );
    // Start in FAULT until first healthy poll.
    fault_bi.set_present_value(1);
    let _ = fault_bi.write_property(
        PropertyIdentifier::ACTIVE_TEXT,
        None,
        PropertyValue::CharacterString("FAULT".into()),
        None,
    );
    let _ = fault_bi.write_property(
        PropertyIdentifier::INACTIVE_TEXT,
        None,
        PropertyValue::CharacterString("OK".into()),
        None,
    );
    db.add(Box::new(fault_bi)).context("add APP-FAULT BI")?;

    let mut point_oids = db.list_objects();
    point_oids.sort_by_key(|o| (o.object_type().to_raw(), o.instance_number()));
    let mut object_list = vec![device_oid];
    object_list.extend(point_oids);

    let mut device = DeviceObject::new(DeviceConfig {
        instance: cfg.instance,
        name: cfg.name.clone(),
        vendor_name: "Open-FDD".into(),
        vendor_id: VENDOR_ID,
        model_name: "openfdd-bacnet-feather-concept".into(),
        application_software_version: env!("CARGO_PKG_VERSION").into(),
        max_apdu_length: 1476,
        ..DeviceConfig::default()
    })
    .context("DeviceObject::new")?;
    device.set_object_list(object_list);
    db.add(Box::new(device)).context("add device")?;

    Ok(db)
}

async fn mirror_state_to_points(
    db: Arc<RwLock<ObjectDatabase>>,
    state: AppStateHandle,
    av_instance: u32,
    av_name: String,
    bi_instance: u32,
    bi_name: String,
    update_secs: u64,
) {
    let av_oid = ObjectIdentifier::new(ObjectType::ANALOG_VALUE, av_instance)
        .expect("hard-coded AV object id");
    let bi_oid = ObjectIdentifier::new(ObjectType::BINARY_INPUT, bi_instance)
        .expect("hard-coded BI object id");

    let mut last_fault: Option<bool> = None;
    let mut last_duct: Option<f64> = None;

    loop {
        tokio::time::sleep(Duration::from_secs(update_secs)).await;

        let snapshot = { state.read().await.clone() };
        let mut db = db.write().await;

        if let Some(temp_f) = snapshot.duct_t {
            if last_duct.map(|v| (v - temp_f).abs() > 1e-6).unwrap_or(true) {
                if let Some(obj) = db.get_mut(&av_oid) {
                    if let Err(err) = obj.write_property(
                        PropertyIdentifier::PRESENT_VALUE,
                        None,
                        PropertyValue::Real(temp_f as f32),
                        Some(16),
                    ) {
                        warn!("failed to update AV:{av_instance} ({av_name}): {err}");
                    } else {
                        info!(
                            "clone AV:{av_instance} \"{av_name}\" = {temp_f:.2} °F (from field poll)"
                        );
                        last_duct = Some(temp_f);
                    }
                }
            }
        }

        let fault_pv: u32 = if snapshot.fault { 1 } else { 0 };
        if last_fault != Some(snapshot.fault) {
            if let Some(obj) = db.get_mut(&bi_oid) {
                // BinaryInput present-value is app-driven via set_present_value, not network write.
                // Downcast isn't available through the trait — use write only when OOS, so we
                // reach through the concrete type stored in the DB by replacing via trait object
                // isn't possible. Use the object's internal path: set OOS, write, clear OOS —
                // too heavy. Prefer reading as Any... ObjectDatabase stores Box<dyn BACnetObject>.
                //
                // BinaryInput only allows PRESENT_VALUE write when out-of-service. Use that.
                let _ = obj.write_property(
                    PropertyIdentifier::OUT_OF_SERVICE,
                    None,
                    PropertyValue::Boolean(true),
                    None,
                );
                if let Err(err) = obj.write_property(
                    PropertyIdentifier::PRESENT_VALUE,
                    None,
                    PropertyValue::Enumerated(fault_pv),
                    None,
                ) {
                    warn!("failed to update BI:{bi_instance} ({bi_name}): {err}");
                } else {
                    let label = if snapshot.fault { "FAULT" } else { "OK" };
                    info!(
                        "status BI:{bi_instance} \"{bi_name}\" = {label} ({})",
                        snapshot.fault_reason
                    );
                    last_fault = Some(snapshot.fault);
                }
                let _ = obj.write_property(
                    PropertyIdentifier::OUT_OF_SERVICE,
                    None,
                    PropertyValue::Boolean(false),
                    None,
                );
            }
        }
    }
}
