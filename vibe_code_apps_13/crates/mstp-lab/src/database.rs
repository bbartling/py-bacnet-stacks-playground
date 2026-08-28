//! Mini-device object database (ported from rusty-bacnet mini-device-revisited).

use bacnet_objects::analog::{AnalogInputObject, AnalogValueObject};
use bacnet_objects::binary::{BinaryInputObject, BinaryValueObject};
use bacnet_objects::database::ObjectDatabase;
use bacnet_objects::device::{DeviceConfig, DeviceObject};
use bacnet_objects::traits::BACnetObject;
use bacnet_types::enums::{ObjectType, PropertyIdentifier};
use bacnet_types::primitives::{ObjectIdentifier, PropertyValue};

pub const VENDOR_ID: u16 = 999;
pub const UNITS_DEGF: u32 = 62;
pub const MSTP_MAX_APDU: u32 = 480;

#[derive(Debug, Clone)]
pub struct MiniDeviceConfig {
    pub instance: u32,
    pub name: String,
}

/// Build the Phase 2 mini-device object database (device + four points).
pub fn build_mini_device_database(
    cfg: &MiniDeviceConfig,
) -> Result<ObjectDatabase, bacnet_types::error::Error> {
    let mut db = ObjectDatabase::new();
    let device_oid = ObjectIdentifier::new(ObjectType::DEVICE, cfg.instance)?;

    let mut read_only_ai = AnalogInputObject::new(1, "read-only-ai", UNITS_DEGF)?;
    read_only_ai.set_description("Simulated Read-Only Analog Input");
    read_only_ai.set_present_value(4.0);
    db.add(Box::new(read_only_ai))?;

    let mut read_only_bi = BinaryInputObject::new(1, "read-only-bi")?;
    read_only_bi.set_description("Simulated Read-Only Binary Input");
    read_only_bi.set_present_value(1);
    db.add(Box::new(read_only_bi))?;

    let mut commandable_av = AnalogValueObject::new(2, "commandable-av", UNITS_DEGF)?;
    commandable_av.set_description("Commandable Analog Value (Simulated)");
    commandable_av.set_present_value(0.0);
    commandable_av.write_property(
        PropertyIdentifier::COV_INCREMENT,
        None,
        PropertyValue::Real(1.0),
        None,
    )?;
    db.add(Box::new(commandable_av))?;

    let mut commandable_bv = BinaryValueObject::new(2, "commandable-bv")?;
    commandable_bv.set_description("Commandable Binary Value (Simulated)");
    commandable_bv.write_property(
        PropertyIdentifier::PRESENT_VALUE,
        None,
        PropertyValue::Enumerated(0),
        None,
    )?;
    db.add(Box::new(commandable_bv))?;

    let mut point_oids = db.list_objects();
    point_oids.sort_by_key(|o| (o.object_type().to_raw(), o.instance_number()));
    let mut object_list = vec![device_oid];
    object_list.extend(point_oids);

    let mut device = DeviceObject::new(DeviceConfig {
        instance: cfg.instance,
        name: cfg.name.clone(),
        vendor_name: "vibe13-mstp-lab".into(),
        vendor_id: VENDOR_ID,
        model_name: "mstp-mini-device".into(),
        application_software_version: env!("CARGO_PKG_VERSION").into(),
        max_apdu_length: MSTP_MAX_APDU,
        ..DeviceConfig::default()
    })?;
    device.set_object_list(object_list);
    db.add(Box::new(device))?;

    Ok(db)
}
