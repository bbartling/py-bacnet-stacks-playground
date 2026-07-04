//! BACnet/IP mini-device — same stack pattern as `openfdd-bacnet-mimic`.
//!
//! Listens on UDP **47808** (0xBAC0), answers Who-Is with I-Am (no periodic spam).
//! Device instance **5000**:
//! - AV:1 `5007-duct-t-clone` — mirrors field DUCT-T
//! - AV:2–5 outdoor weather (Open-Meteo)
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

use crate::app_config::{
    ServerConfig, WeatherConfig, TEMP_UNITS_DEGREES_F, UNITS_MILES_PER_HOUR, UNITS_PERCENT_RH,
    VENDOR_ID,
};
use crate::latest::AppStateHandle;
use crate::network::{free_udp_port, resolve_network, verify_udp_bind};

/// Owns the BACnet/IP mini-device server.
pub struct MiniDeviceRuntime {
    server: Arc<Mutex<BACnetServer<BipTransport>>>,
}

impl MiniDeviceRuntime {
    /// Start mini-device and mirror `state` into clone AV, weather AVs, APP-FAULT BI.
    pub async fn start(
        cfg: &ServerConfig,
        weather: &WeatherConfig,
        state: AppStateHandle,
    ) -> Result<Self> {
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
            "weather points: AV:{} \"{}\" AV:{} \"{}\" AV:{} \"{}\" AV:{} \"{}\" (city=\"{}\")",
            weather.temp_object_instance,
            weather.temp_point_name,
            weather.humidity_object_instance,
            weather.humidity_point_name,
            weather.wind_object_instance,
            weather.wind_point_name,
            weather.dewpoint_object_instance,
            weather.dewpoint_point_name,
            weather.city
        );
        info!(
            "status point: binaryInput:{} \"{}\" (active=FAULT)",
            cfg.status_object_instance, cfg.status_point_name
        );

        free_udp_port(cfg.port);
        verify_udp_bind(net.bind_ip, cfg.port).context("UDP bind check")?;

        let db = build_database(cfg, weather)?;
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
            MirrorIds {
                duct_av: cfg.temp_object_instance,
                duct_name: cfg.temp_point_name.clone(),
                wx_temp_av: weather.temp_object_instance,
                wx_temp_name: weather.temp_point_name.clone(),
                wx_rh_av: weather.humidity_object_instance,
                wx_rh_name: weather.humidity_point_name.clone(),
                wx_wind_av: weather.wind_object_instance,
                wx_wind_name: weather.wind_point_name.clone(),
                wx_dp_av: weather.dewpoint_object_instance,
                wx_dp_name: weather.dewpoint_point_name.clone(),
                fault_bi: cfg.status_object_instance,
                fault_name: cfg.status_point_name.clone(),
            },
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

struct MirrorIds {
    duct_av: u32,
    duct_name: String,
    wx_temp_av: u32,
    wx_temp_name: String,
    wx_rh_av: u32,
    wx_rh_name: String,
    wx_wind_av: u32,
    wx_wind_name: String,
    wx_dp_av: u32,
    wx_dp_name: String,
    fault_bi: u32,
    fault_name: String,
}

fn add_av(
    db: &mut ObjectDatabase,
    instance: u32,
    name: &str,
    units: u32,
    description: &str,
    initial: f32,
) -> Result<()> {
    let mut av = AnalogValueObject::new(instance, name, units).context("AnalogValueObject::new")?;
    av.set_description(description);
    av.set_present_value(initial);
    db.add(Box::new(av)).context("add AV")?;
    Ok(())
}

fn build_database(cfg: &ServerConfig, weather: &WeatherConfig) -> Result<ObjectDatabase> {
    let mut db = ObjectDatabase::new();
    let device_oid = ObjectIdentifier::new(ObjectType::DEVICE, cfg.instance)?;

    add_av(
        &mut db,
        cfg.temp_object_instance,
        &cfg.temp_point_name,
        TEMP_UNITS_DEGREES_F,
        "POC clone of field device 5007 analogInput:1192 (DUCT-T) — updated from poller",
        0.0,
    )?;

    add_av(
        &mut db,
        weather.temp_object_instance,
        &weather.temp_point_name,
        TEMP_UNITS_DEGREES_F,
        "Outdoor dry-bulb from Open-Meteo (fallback when API fails)",
        weather.fallback_temp_f as f32,
    )?;
    add_av(
        &mut db,
        weather.humidity_object_instance,
        &weather.humidity_point_name,
        UNITS_PERCENT_RH,
        "Outdoor relative humidity from Open-Meteo",
        weather.fallback_humidity as f32,
    )?;
    add_av(
        &mut db,
        weather.wind_object_instance,
        &weather.wind_point_name,
        UNITS_MILES_PER_HOUR,
        "Outdoor wind speed from Open-Meteo",
        weather.fallback_wind_mph as f32,
    )?;
    add_av(
        &mut db,
        weather.dewpoint_object_instance,
        &weather.dewpoint_point_name,
        TEMP_UNITS_DEGREES_F,
        "Outdoor dewpoint (°F) from dry-bulb + RH (Magnus) — economizer / free cooling",
        crate::weather::dewpoint_f_from_db_rh(weather.fallback_temp_f, weather.fallback_humidity)
            as f32,
    )?;

    let mut fault_bi = BinaryInputObject::new(cfg.status_object_instance, &cfg.status_point_name)
        .context("BinaryInputObject::new")?;
    fault_bi.set_description(
        "Application fault: active=true when field BACnet reads fail, data is stale, or poller crashed",
    );
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

fn write_av_real(
    db: &mut ObjectDatabase,
    instance: u32,
    name: &str,
    value: f64,
    last: &mut Option<f64>,
    label: &str,
) {
    if last.map(|v| (v - value).abs() < 1e-3).unwrap_or(false) {
        return;
    }
    let oid = match ObjectIdentifier::new(ObjectType::ANALOG_VALUE, instance) {
        Ok(o) => o,
        Err(_) => return,
    };
    if let Some(obj) = db.get_mut(&oid) {
        if let Err(err) = obj.write_property(
            PropertyIdentifier::PRESENT_VALUE,
            None,
            PropertyValue::Real(value as f32),
            Some(16),
        ) {
            warn!("failed to update AV:{instance} ({name}): {err}");
        } else {
            info!("weather AV:{instance} \"{name}\" = {value:.2} ({label})");
            *last = Some(value);
        }
    }
}

async fn mirror_state_to_points(
    db: Arc<RwLock<ObjectDatabase>>,
    state: AppStateHandle,
    ids: MirrorIds,
    update_secs: u64,
) {
    let duct_oid = ObjectIdentifier::new(ObjectType::ANALOG_VALUE, ids.duct_av)
        .expect("duct AV object id");
    let bi_oid = ObjectIdentifier::new(ObjectType::BINARY_INPUT, ids.fault_bi)
        .expect("fault BI object id");

    let mut last_fault: Option<bool> = None;
    let mut last_duct: Option<f64> = None;
    let mut last_wx_t: Option<f64> = None;
    let mut last_wx_rh: Option<f64> = None;
    let mut last_wx_wind: Option<f64> = None;
    let mut last_wx_dp: Option<f64> = None;

    loop {
        tokio::time::sleep(Duration::from_secs(update_secs)).await;

        let snapshot = { state.read().await.clone() };
        let mut db = db.write().await;

        if let Some(temp_f) = snapshot.duct_t {
            if last_duct.map(|v| (v - temp_f).abs() > 1e-6).unwrap_or(true) {
                if let Some(obj) = db.get_mut(&duct_oid) {
                    if let Err(err) = obj.write_property(
                        PropertyIdentifier::PRESENT_VALUE,
                        None,
                        PropertyValue::Real(temp_f as f32),
                        Some(16),
                    ) {
                        warn!(
                            "failed to update AV:{} ({}): {err}",
                            ids.duct_av, ids.duct_name
                        );
                    } else {
                        info!(
                            "clone AV:{} \"{}\" = {temp_f:.2} °F (from field poll)",
                            ids.duct_av, ids.duct_name
                        );
                        last_duct = Some(temp_f);
                    }
                }
            }
        }

        if let Some(wx) = &snapshot.weather {
            let src = if wx.from_api { "open-meteo" } else { "fallback" };
            write_av_real(
                &mut db,
                ids.wx_temp_av,
                &ids.wx_temp_name,
                wx.temp_f,
                &mut last_wx_t,
                src,
            );
            write_av_real(
                &mut db,
                ids.wx_rh_av,
                &ids.wx_rh_name,
                wx.humidity,
                &mut last_wx_rh,
                src,
            );
            write_av_real(
                &mut db,
                ids.wx_wind_av,
                &ids.wx_wind_name,
                wx.wind_mph,
                &mut last_wx_wind,
                src,
            );
            write_av_real(
                &mut db,
                ids.wx_dp_av,
                &ids.wx_dp_name,
                wx.dewpoint_f,
                &mut last_wx_dp,
                src,
            );
        }

        let fault_pv: u32 = if snapshot.fault { 1 } else { 0 };
        if last_fault != Some(snapshot.fault) {
            if let Some(obj) = db.get_mut(&bi_oid) {
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
                    warn!(
                        "failed to update BI:{} ({}): {err}",
                        ids.fault_bi, ids.fault_name
                    );
                } else {
                    let label = if snapshot.fault { "FAULT" } else { "OK" };
                    info!(
                        "status BI:{} \"{}\" = {label} ({})",
                        ids.fault_bi, ids.fault_name, snapshot.fault_reason
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
