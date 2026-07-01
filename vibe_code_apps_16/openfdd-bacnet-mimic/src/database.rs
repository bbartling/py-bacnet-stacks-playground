//! BACnet object database — same points as Open-FDD `bacnet_server_runtime.rs`.

use bacnet_objects::analog::AnalogValueObject;
use bacnet_objects::binary::BinaryValueObject;
use bacnet_objects::database::ObjectDatabase;
use bacnet_objects::device::{DeviceConfig, DeviceObject};
use bacnet_objects::traits::BACnetObject;
use bacnet_types::enums::{ObjectType, PropertyIdentifier};
use bacnet_types::primitives::{ObjectIdentifier, PropertyValue};

use crate::config::OPENFDD_VENDOR_ID;

const UNITS_NONE: u32 = 95;
const UNITS_DEGF: u32 = 62;
const UNITS_PCT: u32 = 98;

/// Build device + diagnostic points for the mimic server.
pub fn build_database(instance: u32, name: &str) -> Result<ObjectDatabase, Box<dyn std::error::Error>> {
    let mut db = ObjectDatabase::new();
    let device_oid = ObjectIdentifier::new(ObjectType::DEVICE, instance)?;

    add_analog(&mut db, 9003, "openfdd-active-fault-count", UNITS_NONE, "Active FDD fault count", 0.0)?;
    add_binary(&mut db, 9004, "openfdd-faults-present", "True when one or more FDD faults are active")?;
    add_binary(
        &mut db,
        9010,
        "openfdd-optimization-enabled",
        "Commandable optimization enable (writable via BACnet or API)",
    )?;

    for (inst, point_name, desc, units, value) in [
        (9101, "outside-air-temperature", "Outside air temperature (placeholder)", UNITS_DEGF, 72.0),
        (9102, "outside-air-humidity", "Outside air humidity (placeholder)", UNITS_PCT, 50.0),
        (9103, "outside-air-dewpoint", "Outside air dewpoint (placeholder)", UNITS_DEGF, 55.0),
    ] {
        add_analog(&mut db, inst, point_name, units, desc, value)?;
    }

    let mut point_oids = db.list_objects();
    point_oids.sort_by_key(|o| (o.object_type().to_raw(), o.instance_number()));

    let mut object_list = vec![device_oid];
    object_list.extend(point_oids);

    let mut device = DeviceObject::new(DeviceConfig {
        instance,
        name: name.to_string(),
        vendor_name: "Open-FDD".into(),
        vendor_id: OPENFDD_VENDOR_ID,
        model_name: "openfdd-bacnet-mimic".into(),
        application_software_version: env!("CARGO_PKG_VERSION").into(),
        max_apdu_length: 1476,
        ..DeviceConfig::default()
    })?;
    device.set_object_list(object_list);
    db.add(Box::new(device))?;

    Ok(db)
}

fn add_analog(
    db: &mut ObjectDatabase,
    instance: u32,
    name: &str,
    units: u32,
    description: &str,
    value: f32,
) -> Result<(), Box<dyn std::error::Error>> {
    let mut av = AnalogValueObject::new(instance, name, units)?;
    av.set_description(description);
    av.set_present_value(value);
    db.add(Box::new(av))?;
    Ok(())
}

fn add_binary(
    db: &mut ObjectDatabase,
    instance: u32,
    name: &str,
    description: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    let mut bv = BinaryValueObject::new(instance, name)?;
    bv.set_description(description);
    bv.write_property(
        PropertyIdentifier::PRESENT_VALUE,
        None,
        PropertyValue::Enumerated(0),
        None,
    )?;
    db.add(Box::new(bv))?;
    Ok(())
}
