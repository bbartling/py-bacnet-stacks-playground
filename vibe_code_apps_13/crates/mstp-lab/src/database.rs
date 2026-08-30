//! Mini-device object database (ported from rusty-bacnet mini-device-revisited).

use bacnet_objects::analog::{AnalogInputObject, AnalogValueObject};
use bacnet_objects::binary::{BinaryInputObject, BinaryValueObject};
use bacnet_objects::database::ObjectDatabase;
use bacnet_objects::device::{DeviceConfig, DeviceObject};
use bacnet_objects::traits::BACnetObject;
use bacnet_types::enums::{ErrorClass, ErrorCode, ObjectType, PropertyIdentifier};
use bacnet_types::error::Error;
use bacnet_types::primitives::{ObjectIdentifier, PropertyValue};

/// Lab placeholder vendor ID — not production-ready.
pub const LAB_VENDOR_ID: u16 = 999;
#[allow(dead_code)]
#[deprecated(note = "use LAB_VENDOR_ID")]
pub const VENDOR_ID: u16 = LAB_VENDOR_ID;
pub const UNITS_DEGF: u32 = 62;
pub const MSTP_MAX_APDU: u32 = 480;

#[derive(Debug, Clone)]
pub struct MiniDeviceConfig {
    pub instance: u32,
    pub name: String,
    pub vendor_id: u16,
}

impl Default for MiniDeviceConfig {
    fn default() -> Self {
        Self {
            instance: 123_001,
            name: "Rust MS/TP Mini Device".to_owned(),
            vendor_id: LAB_VENDOR_ID,
        }
    }
}

/// Build the Phase 2 mini-device object database (device + four points).
pub fn build_mini_device_database(cfg: &MiniDeviceConfig) -> Result<ObjectDatabase, Error> {
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
        vendor_id: cfg.vendor_id,
        model_name: "mstp-mini-device".into(),
        application_software_version: env!("CARGO_PKG_VERSION").into(),
        max_apdu_length: MSTP_MAX_APDU,
        ..DeviceConfig::default()
    })?;
    device.set_object_list(object_list);
    db.add(Box::new(device))?;

    Ok(db)
}

/// Trusted local simulation update for AI:1 / BI:1 using `set_present_value`.
///
/// Network WriteProperty to these inputs remains denied while in-service.
/// Replaces the objects in-place because `dyn BACnetObject` has no downcast.
pub fn apply_simulated_inputs(
    db: &mut ObjectDatabase,
    active: bool,
    ai_value: f32,
) -> Result<(), Error> {
    let ai_oid = ObjectIdentifier::new(ObjectType::ANALOG_INPUT, 1)?;
    let bi_oid = ObjectIdentifier::new(ObjectType::BINARY_INPUT, 1)?;

    let _ = db.remove(&ai_oid);
    let mut ai = AnalogInputObject::new(1, "read-only-ai", UNITS_DEGF)?;
    ai.set_description("Simulated Read-Only Analog Input");
    ai.set_present_value(ai_value);
    db.add(Box::new(ai))?;

    let _ = db.remove(&bi_oid);
    let mut bi = BinaryInputObject::new(1, "read-only-bi")?;
    bi.set_description("Simulated Read-Only Binary Input");
    bi.set_present_value(u32::from(active));
    db.add(Box::new(bi))?;

    Ok(())
}

/// Assert network-style WriteProperty to AI:1 is denied (in-service).
pub fn network_write_ai_denied(db: &mut ObjectDatabase) -> Result<(), Error> {
    let ai = ObjectIdentifier::new(ObjectType::ANALOG_INPUT, 1)?;
    let obj = db.get_mut(&ai).ok_or(Error::Protocol {
        class: ErrorClass::OBJECT.to_raw() as u32,
        code: ErrorCode::UNKNOWN_OBJECT.to_raw() as u32,
    })?;
    if obj
        .write_property(
            PropertyIdentifier::PRESENT_VALUE,
            None,
            PropertyValue::Real(99.0),
            None,
        )
        .is_ok()
    {
        return Err(Error::Encoding(
            "AI:1 WriteProperty unexpectedly succeeded".into(),
        ));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn vendor_id_consistent_in_device_object() {
        let cfg = MiniDeviceConfig {
            vendor_id: 4242,
            ..Default::default()
        };
        let db = build_mini_device_database(&cfg).unwrap();
        let oid = ObjectIdentifier::new(ObjectType::DEVICE, cfg.instance).unwrap();
        let obj = db.get(&oid).unwrap();
        let v = obj
            .read_property(PropertyIdentifier::VENDOR_IDENTIFIER, None)
            .unwrap();
        assert_eq!(v, PropertyValue::Unsigned(u64::from(cfg.vendor_id)));
    }

    #[test]
    fn local_simulation_updates_ai_bi_network_denied() {
        let mut db = build_mini_device_database(&MiniDeviceConfig::default()).unwrap();
        apply_simulated_inputs(&mut db, false, 12.5).unwrap();
        let ai = ObjectIdentifier::new(ObjectType::ANALOG_INPUT, 1).unwrap();
        let bi = ObjectIdentifier::new(ObjectType::BINARY_INPUT, 1).unwrap();
        assert_eq!(
            db.get(&ai)
                .unwrap()
                .read_property(PropertyIdentifier::PRESENT_VALUE, None)
                .unwrap(),
            PropertyValue::Real(12.5)
        );
        assert_eq!(
            db.get(&bi)
                .unwrap()
                .read_property(PropertyIdentifier::PRESENT_VALUE, None)
                .unwrap(),
            PropertyValue::Enumerated(0)
        );
        network_write_ai_denied(&mut db).unwrap();
    }

    #[test]
    fn av_priority_write_and_relinquish() {
        let mut db = build_mini_device_database(&MiniDeviceConfig::default()).unwrap();
        let av = ObjectIdentifier::new(ObjectType::ANALOG_VALUE, 2).unwrap();
        let obj = db.get_mut(&av).unwrap();
        obj.write_property(
            PropertyIdentifier::PRESENT_VALUE,
            None,
            PropertyValue::Real(75.0),
            Some(8),
        )
        .unwrap();
        assert_eq!(
            obj.read_property(PropertyIdentifier::PRESENT_VALUE, None)
                .unwrap(),
            PropertyValue::Real(75.0)
        );
        obj.write_property(
            PropertyIdentifier::PRESENT_VALUE,
            None,
            PropertyValue::Null,
            Some(8),
        )
        .unwrap();
        let after = obj
            .read_property(PropertyIdentifier::PRESENT_VALUE, None)
            .unwrap();
        assert_ne!(after, PropertyValue::Real(75.0));
    }

    #[test]
    fn object_list_has_device_and_four_points() {
        let db = build_mini_device_database(&MiniDeviceConfig::default()).unwrap();
        assert_eq!(db.list_objects().len(), 5, "device + AI + BI + AV + BV");
        let oid = ObjectIdentifier::new(ObjectType::DEVICE, 123_001).unwrap();
        let list = db
            .get(&oid)
            .unwrap()
            .read_property(PropertyIdentifier::OBJECT_LIST, None)
            .unwrap();
        // PropertyValue shape varies by pin; ensure we got a non-null list payload
        assert!(!matches!(list, PropertyValue::Null));
    }

    #[test]
    fn max_apdu_is_standard_frame_480() {
        let db = build_mini_device_database(&MiniDeviceConfig::default()).unwrap();
        let oid = ObjectIdentifier::new(ObjectType::DEVICE, 123_001).unwrap();
        let v = db
            .get(&oid)
            .unwrap()
            .read_property(PropertyIdentifier::MAX_APDU_LENGTH_ACCEPTED, None)
            .unwrap();
        assert_eq!(v, PropertyValue::Unsigned(u64::from(MSTP_MAX_APDU)));
    }
}
