//! BACnet/IP mini-device server (demo temp on analogInput:1).

use std::sync::Arc;
use std::time::Duration;

use anyhow::{Context, Result};
use bacnet_objects::analog::AnalogInputObject;
use bacnet_objects::database::ObjectDatabase;
use bacnet_objects::device::{DeviceConfig, DeviceObject};
use bacnet_server::server::BACnetServer;
use bacnet_transport::bip::BipTransport;
use bacnet_types::enums::{ObjectType, PropertyIdentifier};
use bacnet_types::primitives::{ObjectIdentifier, PropertyValue};
use tokio::sync::{Mutex, RwLock};
use tracing::{info, warn};

use crate::app_config::{ServerConfig, TEMP_UNITS_DEGREES_F, VENDOR_ID};
use crate::network::{free_udp_port, resolve_network, verify_udp_bind};

/// Owns the BACnet/IP mini-device server.
pub struct MiniDeviceRuntime {
    server: Arc<Mutex<BACnetServer<BipTransport>>>,
}

impl MiniDeviceRuntime {
    /// Start mini-device + present-value updater for AI:1.
    pub async fn start(cfg: &ServerConfig) -> Result<Self> {
        let net = resolve_network(cfg.address, cfg.broadcast, &cfg.nic);
        info!(
            "starting BACnet mini-device {} instance={} UDP :{}",
            cfg.name, cfg.instance, cfg.port
        );
        info!(
            "host_ip={} broadcast={} bind={}",
            net.device_ip, net.broadcast, net.bind_ip
        );
        info!(
            "point: analogInput:{} {} (update every {}s)",
            cfg.temp_object_instance, cfg.temp_point_name, cfg.value_update_secs
        );

        free_udp_port(cfg.port);
        verify_udp_bind(net.bind_ip, cfg.port).context("UDP bind check")?;

        let db = build_database(cfg)?;

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

        if let Err(err) = server.broadcast_i_am().await {
            warn!("startup I-Am failed: {err}");
        } else {
            info!("startup I-Am sent (YABE / Workbench can discover this device)");
        }

        let server = Arc::new(Mutex::new(server));

        {
            let server = Arc::clone(&server);
            let instance = cfg.instance;
            tokio::spawn(async move {
                loop {
                    tokio::time::sleep(Duration::from_secs(60)).await;
                    let guard = server.lock().await;
                    if let Err(err) = guard.broadcast_i_am().await {
                        warn!("periodic I-Am failed: {err}");
                    } else {
                        info!("periodic I-Am sent for device {instance}");
                    }
                }
            });
        }

        let ai_inst = cfg.temp_object_instance;
        let update_secs = cfg.value_update_secs.max(1);
        tokio::spawn(update_temperature_loop(db_for_updates, ai_inst, update_secs));

        Ok(Self { server })
    }

    pub async fn shutdown(&mut self) {
        info!("stopping BACnet mini-device server");
        let _ = self.server.lock().await.stop().await;
    }
}

fn build_database(cfg: &ServerConfig) -> Result<ObjectDatabase> {
    let mut db = ObjectDatabase::new();

    let mut temp = AnalogInputObject::new(
        cfg.temp_object_instance,
        &cfg.temp_point_name,
        TEMP_UNITS_DEGREES_F,
    )
    .context("AnalogInputObject::new")?;
    temp.set_description("Demo temp sensor — updated in-process every few seconds");
    temp.set_present_value(72.0);
    db.add(Box::new(temp)).context("add AI")?;

    let device_oid = ObjectIdentifier::new(ObjectType::DEVICE, cfg.instance)?;
    let temp_oid =
        ObjectIdentifier::new(ObjectType::ANALOG_INPUT, cfg.temp_object_instance)?;

    let mut device = DeviceObject::new(DeviceConfig {
        instance: cfg.instance,
        name: cfg.name.clone(),
        vendor_name: "Open-FDD concept bench".into(),
        vendor_id: VENDOR_ID,
        model_name: "openfdd-bacnet-feather-concept".into(),
        application_software_version: env!("CARGO_PKG_VERSION").into(),
        ..DeviceConfig::default()
    })
    .context("DeviceObject::new")?;
    device.set_object_list(vec![device_oid, temp_oid]);
    db.add(Box::new(device)).context("add device")?;

    Ok(db)
}

async fn update_temperature_loop(
    db: Arc<RwLock<ObjectDatabase>>,
    ai_instance: u32,
    update_secs: u64,
) {
    let temp_oid = ObjectIdentifier::new(ObjectType::ANALOG_INPUT, ai_instance)
        .expect("hard-coded AI object id");

    let mut step: u32 = 0;
    loop {
        tokio::time::sleep(Duration::from_secs(update_secs)).await;
        let temp_f = 72.0 + ((step % 20) as f32 * 0.25);
        step = step.wrapping_add(1);

        let mut db = db.write().await;
        if let Some(obj) = db.get_mut(&temp_oid) {
            if let Err(err) = obj.write_property(
                PropertyIdentifier::PRESENT_VALUE,
                None,
                PropertyValue::Real(temp_f),
                None,
            ) {
                warn!("failed to update AI:{ai_instance}: {err}");
            } else {
                info!("server updated AI:{ai_instance} present-value={temp_f:.2} °F");
            }
        } else {
            warn!("AI:{ai_instance} missing from object database");
        }
    }
}
