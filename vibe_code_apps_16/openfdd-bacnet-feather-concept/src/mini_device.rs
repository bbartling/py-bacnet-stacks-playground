//! BACnet/IP mini-device — same stack pattern as `openfdd-bacnet-mimic`.
//!
//! Listens on UDP **47808** (0xBAC0), answers Who-Is with I-Am (no periodic spam).
//! Device instance **5000**, one AV that mirrors field DUCT-T.

use std::sync::Arc;
use std::time::Duration;

use anyhow::{Context, Result};
use bacnet_objects::analog::AnalogValueObject;
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
use crate::latest::LatestHandle;
use crate::network::{free_udp_port, resolve_network, verify_udp_bind};

/// Owns the BACnet/IP mini-device server.
pub struct MiniDeviceRuntime {
    server: Arc<Mutex<BACnetServer<BipTransport>>>,
}

impl MiniDeviceRuntime {
    /// Start mini-device (mimic-style) and mirror `latest` into the clone AV.
    pub async fn start(cfg: &ServerConfig, latest: LatestHandle) -> Result<Self> {
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
            "clone point: analogValue:{} \"{}\" (mirrors field poll every {}s)",
            cfg.temp_object_instance, cfg.temp_point_name, cfg.value_update_secs
        );

        // Same as mimic --replace-existing
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

        // Passive responds to Who-Is automatically (like mimic). No startup/periodic I-Am.

        let server = Arc::new(Mutex::new(server));

        let av_inst = cfg.temp_object_instance;
        let update_secs = cfg.value_update_secs.max(1);
        let point_name = cfg.temp_point_name.clone();
        tokio::spawn(mirror_latest_to_av(
            db_for_updates,
            latest,
            av_inst,
            update_secs,
            point_name,
        ));

        info!("listening — Workbench/YABE Who-Is should show device {}", cfg.instance);
        Ok(Self { server })
    }

    pub async fn shutdown(&mut self) {
        info!("stopping BACnet mini-device server");
        let _ = self.server.lock().await.stop().await;
    }
}

/// Build device + clone AV — object-list pattern matches openfdd-bacnet-mimic.
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

    // Same object-list construction as mimic (required for Workbench point discover).
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

async fn mirror_latest_to_av(
    db: Arc<RwLock<ObjectDatabase>>,
    latest: LatestHandle,
    av_instance: u32,
    update_secs: u64,
    point_name: String,
) {
    let av_oid = ObjectIdentifier::new(ObjectType::ANALOG_VALUE, av_instance)
        .expect("hard-coded AV object id");

    loop {
        tokio::time::sleep(Duration::from_secs(update_secs)).await;

        let reading = { *latest.read().await };
        let Some(reading) = reading else {
            continue;
        };

        let temp_f = reading.present_value as f32;
        let mut db = db.write().await;
        if let Some(obj) = db.get_mut(&av_oid) {
            if let Err(err) = obj.write_property(
                PropertyIdentifier::PRESENT_VALUE,
                None,
                PropertyValue::Real(temp_f),
                Some(16),
            ) {
                warn!("failed to update AV:{av_instance} ({point_name}): {err}");
            } else {
                info!(
                    "clone AV:{av_instance} \"{point_name}\" = {temp_f:.2} °F (from field poll)"
                );
            }
        }
    }
}
