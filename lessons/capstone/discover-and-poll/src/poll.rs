use anyhow::{Context, Result};
use chrono::Utc;
use csv::Writer;
use std::fs::File;
use std::path::Path;

/// Stub poll — writes CSV rows so Day 46 `commission_snapshot.csv` shape is testable.
/// Replace ReadProperty/RPM with rusty-bacnet (Day 42–43).
pub fn run(device: u32, host: &str, out_path: &str, objects: &[String]) -> Result<()> {
    if objects.is_empty() {
        anyhow::bail!("pass at least one --objects analogInput:1");
    }

    let path = Path::new(out_path);
    if let Some(parent) = path.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent)?;
        }
    }

    let file = File::create(path).with_context(|| format!("create {out_path}"))?;
    let mut w = Writer::from_writer(file);
    w.write_record(["device", "object", "pv", "timestamp", "host", "note"])?;

    let now = Utc::now().to_rfc3339();
    for obj in objects {
        w.write_record([
            device.to_string(),
            obj.clone(),
            "NaN".to_string(),
            now.clone(),
            host.to_string(),
            "stub-until-rusty-bacnet-read".to_string(),
        ])?;
    }
    w.flush()?;

    eprintln!("wrote {out_path} ({host} device {device})");
    eprintln!("next: cargo run -- poll --device {device} after wiring rusty-bacnet ReadProperty");
    Ok(())
}
