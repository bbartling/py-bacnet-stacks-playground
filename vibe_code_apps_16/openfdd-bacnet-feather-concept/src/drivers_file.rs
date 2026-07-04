//! BAS driver files — one TOML per device under `config/drivers/devices/`.
//!
//! - `config/config.toml` — app + poller scheduler settings
//! - `config/drivers/settings.toml` — scan metadata (no points)
//! - `config/drivers/devices/<instance>-<name>.toml` — one device + `[[points]]`
//! - `config/drivers/catalog.md` — human/AI tables + import TOML for `--apply-catalog`
//!
//! Delete a device file to exclude it from polling entirely.

use std::collections::HashMap;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result};
use serde::Deserialize;

use crate::app_config::{DeviceConfig, DevicePointConfig};

pub const DEFAULT_DEVICES_DIR: &str = "config/drivers/devices";
pub const DEFAULT_SETTINGS_PATH: &str = "config/drivers/settings.toml";
pub const DEFAULT_CATALOG_PATH: &str = "config/drivers/catalog.md";

/// Multi-device bundle parsed from catalog import (`[[devices]]` / `[[devices.points]]`).
#[derive(Debug, Clone, Default, Deserialize)]
pub struct DriversFile {
    #[serde(default)]
    pub devices: Vec<DeviceConfig>,
}

impl DriversFile {
    pub fn load(path: &Path) -> Result<Self> {
        let text = std::fs::read_to_string(path)
            .with_context(|| format!("reading drivers file {}", path.display()))?;
        toml::from_str(&text).with_context(|| format!("parsing drivers file {}", path.display()))
    }
}

/// Load poll devices from `devices_dir`, else built-in `fallback` (empty in normal use).
pub fn load_devices_or(fallback: Vec<DeviceConfig>, devices_dir: &Path) -> Vec<DeviceConfig> {
    match load_devices_from_dir(devices_dir) {
        Ok(devices) if !devices.is_empty() => {
            tracing::info!(
                "loaded {} device driver(s) from {}",
                devices.len(),
                devices_dir.display()
            );
            devices
        }
        Ok(_) => {
            tracing::warn!(
                "{} has no device files — run bas_scan or add *.toml under devices/",
                devices_dir.display()
            );
            fallback
        }
        Err(err) => {
            tracing::warn!(
                "could not load {} ({err:#}) — using built-in defaults",
                devices_dir.display()
            );
            fallback
        }
    }
}

pub fn load_devices_from_dir(dir: &Path) -> Result<Vec<DeviceConfig>> {
    if !dir.is_dir() {
        anyhow::bail!("{} is not a directory", dir.display());
    }
    let mut paths: Vec<PathBuf> = std::fs::read_dir(dir)?
        .filter_map(|e| e.ok())
        .map(|e| e.path())
        .filter(|p| p.extension().is_some_and(|x| x == "toml"))
        .collect();
    paths.sort();

    let mut devices = Vec::with_capacity(paths.len());
    for path in paths {
        let text = std::fs::read_to_string(&path)
            .with_context(|| format!("reading device driver {}", path.display()))?;
        let dev: DeviceConfig = toml::from_str(&text).with_context(|| {
            format!(
                "parsing device driver {} (expect top-level device fields + [[points]])",
                path.display()
            )
        })?;
        devices.push(dev);
    }
    Ok(devices)
}

pub fn device_slug(name: &str) -> String {
    let s: String = name
        .chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() || c == '-' || c == '_' {
                c
            } else if c.is_whitespace() {
                '-'
            } else {
                '_'
            }
        })
        .collect();
    let s = s.trim_matches('-').to_ascii_lowercase();
    if s.is_empty() {
        "device".into()
    } else {
        s
    }
}

pub fn device_filename(device: &DeviceConfig) -> String {
    format!("{}-{}.toml", device.device_instance, device_slug(&device.name))
}

/// Preserve `enabled=false` (and critical/interval/offset) from previous drivers.
pub fn merge_enabled_flags(scanned: Vec<DeviceConfig>, previous: &[DeviceConfig]) -> Vec<DeviceConfig> {
    let prev_dev: HashMap<u32, &DeviceConfig> = previous
        .iter()
        .map(|d| (d.device_instance, d))
        .collect();

    scanned
        .into_iter()
        .map(|mut d| {
            if let Some(old) = prev_dev.get(&d.device_instance) {
                d.enabled = old.enabled;
                d.critical = old.critical;
                if old.interval_secs.is_some() {
                    d.interval_secs = old.interval_secs;
                }
                d.offset_secs = old.offset_secs;
                let prev_pts: HashMap<(String, u32), &DevicePointConfig> = old
                    .points
                    .iter()
                    .map(|p| ((p.object_type.to_ascii_lowercase(), p.object_instance), p))
                    .collect();
                for p in &mut d.points {
                    let key = (p.object_type.to_ascii_lowercase(), p.object_instance);
                    if let Some(old_p) = prev_pts.get(&key) {
                        p.enabled = old_p.enabled;
                        if !old_p.point_name.is_empty() {
                            p.point_name = old_p.point_name.clone();
                        }
                        if !old_p.units.is_empty() {
                            p.units = old_p.units.clone();
                        }
                    }
                }
            }
            d
        })
        .collect()
}

fn toml_escape(s: &str) -> String {
    s.replace('\\', "\\\\").replace('"', "\\\"")
}

/// One device file — `[[points]]` instead of `[[devices.points]]`.
pub fn emit_device_toml(device: &DeviceConfig, header_extra: Option<&str>) -> String {
    let mut out = String::new();
    out.push_str("# =============================================================================\n");
    out.push_str(&format!(
        "# Device: {} (BACnet instance {})\n",
        device.name, device.device_instance
    ));
    out.push_str("# =============================================================================\n");
    out.push_str("# Delete this file to remove the device from polling.\n");
    out.push_str("# Set enabled = false to keep the file but skip polls.\n");
    out.push_str("# Points use [[points]] — this file is only for this one device.\n");
    if let Some(extra) = header_extra {
        for line in extra.lines() {
            out.push_str("# ");
            out.push_str(line);
            out.push('\n');
        }
    }
    out.push_str("# =============================================================================\n\n");

    out.push_str(&format!("name = \"{}\"\n", toml_escape(&device.name)));
    out.push_str(&format!("enabled = {}\n", device.enabled));
    out.push_str(&format!("device_instance = {}\n", device.device_instance));
    out.push_str(&format!("host = \"{}\"\n", device.host));
    out.push_str(&format!("port = {}\n", device.port));
    if let Some(net) = device.mstp_network {
        out.push_str(&format!("mstp_network = {net}\n"));
    }
    if let Some(mac) = &device.mstp_mac {
        let bytes: Vec<String> = mac.iter().map(|b| b.to_string()).collect();
        out.push_str(&format!("mstp_mac = [{}]\n", bytes.join(", ")));
    }
    if let Some(iv) = device.interval_secs {
        out.push_str(&format!("interval_secs = {iv}\n"));
    }
    out.push_str(&format!("offset_secs = {}\n", device.offset_secs));
    out.push_str(&format!("critical = {}\n", device.critical));
    out.push('\n');

    for p in &device.points {
        out.push_str("[[points]]\n");
        out.push_str(&format!("enabled = {}\n", p.enabled));
        out.push_str(&format!(
            "object_type = \"{}\"\n",
            toml_escape(&p.object_type)
        ));
        out.push_str(&format!("object_instance = {}\n", p.object_instance));
        out.push_str(&format!(
            "point_name = \"{}\"\n",
            toml_escape(&p.point_name)
        ));
        out.push_str(&format!("units = \"{}\"\n", toml_escape(&p.units)));
        out.push('\n');
    }
    out
}

/// Multi-device import TOML (`[[devices]]`) for catalog `--apply-catalog`.
pub fn emit_drivers_toml(devices: &[DeviceConfig], header_extra: &str) -> String {
    let mut out = String::new();
    out.push_str("# Catalog import bundle — splits into config/drivers/devices/*.toml on apply\n");
    if !header_extra.is_empty() {
        for line in header_extra.lines() {
            out.push_str("# ");
            out.push_str(line);
            out.push('\n');
        }
    }
    out.push('\n');

    for d in devices {
        out.push_str("[[devices]]\n");
        out.push_str(&format!("name = \"{}\"\n", toml_escape(&d.name)));
        out.push_str(&format!("enabled = {}\n", d.enabled));
        out.push_str(&format!("device_instance = {}\n", d.device_instance));
        out.push_str(&format!("host = \"{}\"\n", d.host));
        out.push_str(&format!("port = {}\n", d.port));
        if let Some(net) = d.mstp_network {
            out.push_str(&format!("mstp_network = {net}\n"));
        }
        if let Some(mac) = &d.mstp_mac {
            let bytes: Vec<String> = mac.iter().map(|b| b.to_string()).collect();
            out.push_str(&format!("mstp_mac = [{}]\n", bytes.join(", ")));
        }
        if let Some(iv) = d.interval_secs {
            out.push_str(&format!("interval_secs = {iv}\n"));
        }
        out.push_str(&format!("offset_secs = {}\n", d.offset_secs));
        out.push_str(&format!("critical = {}\n", d.critical));
        out.push('\n');

        for p in &d.points {
            out.push_str("[[devices.points]]\n");
            out.push_str(&format!("enabled = {}\n", p.enabled));
            out.push_str(&format!(
                "object_type = \"{}\"\n",
                toml_escape(&p.object_type)
            ));
            out.push_str(&format!("object_instance = {}\n", p.object_instance));
            out.push_str(&format!(
                "point_name = \"{}\"\n",
                toml_escape(&p.point_name)
            ));
            out.push_str(&format!("units = \"{}\"\n", toml_escape(&p.units)));
            out.push('\n');
        }
    }
    out
}

pub fn emit_settings_toml(header_extra: &str) -> String {
    let mut out = String::new();
    out.push_str("# =============================================================================\n");
    out.push_str("# BAS driver bundle settings (scan metadata — not polled)\n");
    out.push_str("# =============================================================================\n");
    out.push_str("# App scheduler (tick_ms, max_concurrent) lives in config/config.toml.\n");
    out.push_str("#\n");
    out.push_str("# Per-device poll targets: config/drivers/devices/<instance>-<name>.toml\n");
    out.push_str("#   - Delete a file → device never loaded\n");
    out.push_str("#   - enabled = false → file kept, polls skipped\n");
    out.push_str("#   - [[points]] with enabled = false → skip individual points\n");
    out.push_str("#\n");
    out.push_str("# Re-scan (preserves enabled flags with --merge):\n");
    out.push_str("#   cargo run --release --bin bas_scan -- --low 1 --high 4194302 --on-bac0 --merge\n");
    out.push_str("#\n");
    out.push_str("# Companion catalog: config/drivers/catalog.md\n");
    if !header_extra.is_empty() {
        out.push_str("#\n");
        for line in header_extra.lines() {
            out.push_str("# ");
            out.push_str(line);
            out.push('\n');
        }
    }
    out.push_str("# =============================================================================\n");
    out
}

/// Markdown catalog for pasting into ChatGPT / agents.
pub fn emit_drivers_catalog_md(devices: &[DeviceConfig], header_extra: &str) -> String {
    let mut out = String::new();
    out.push_str("# BAS driver catalog (AI / human editable)\n\n");
    out.push_str("Paste this file into ChatGPT or Cursor and ask:\n");
    out.push_str("> Keep only the points we need for FDD / trending; set `enabled = false` on the rest.\n\n");
    out.push_str("## Workflow\n\n");
    out.push_str("1. Edit per-device files under `config/drivers/devices/` (recommended), **or**\n");
    out.push_str("2. Edit the import TOML block at the bottom and apply:\n");
    out.push_str("   `cargo run --release --bin bas_scan -- --apply-catalog config/drivers/catalog.md`\n");
    out.push_str("3. **Delete** a device `.toml` file to remove it from polling entirely.\n");
    out.push_str("4. Restart: `cargo run --release --bin bacnet_app`\n\n");
    out.push_str("### Per-device files\n\n");
    for d in devices {
        out.push_str(&format!(
            "- `config/drivers/devices/{}` — {} ({} points)\n",
            device_filename(d),
            d.name,
            d.points.len()
        ));
    }
    out.push('\n');
    if !header_extra.is_empty() {
        out.push_str("## Scan metadata\n\n```\n");
        out.push_str(header_extra);
        out.push_str("\n```\n\n");
    }

    out.push_str("## Device summary\n\n");
    out.push_str("| enabled | name | instance | host | routed | points (enabled/total) | file |\n");
    out.push_str("| --- | --- | ---: | --- | --- | ---: | --- |\n");
    for d in devices {
        let en = d.points.iter().filter(|p| p.enabled).count();
        let routed = if d.mstp_mac.is_some() { "yes" } else { "no" };
        out.push_str(&format!(
            "| {} | {} | {} | {}:{} | {routed} | {en}/{} | `{}` |\n",
            d.enabled,
            d.name,
            d.device_instance,
            d.host,
            d.port,
            d.points.len(),
            device_filename(d)
        ));
    }
    out.push('\n');

    for d in devices {
        out.push_str(&format!(
            "## Device `{}` (instance {}) — `devices/{}`\n\n",
            d.name,
            d.device_instance,
            device_filename(d)
        ));
        out.push_str("| enabled | point_name | object_type | object_instance | units |\n");
        out.push_str("| --- | --- | --- | ---: | --- |\n");
        for p in &d.points {
            out.push_str(&format!(
                "| {} | {} | {} | {} | {} |\n",
                p.enabled, p.point_name, p.object_type, p.object_instance, p.units
            ));
        }
        out.push('\n');
    }

    out.push_str("## Import TOML (apply this block to regenerate device files)\n\n");
    out.push_str("```toml\n");
    out.push_str(&emit_drivers_toml(devices, header_extra));
    out.push_str("```\n");
    out
}

/// Extract the first ```toml ... ``` fence from a catalog markdown file.
pub fn extract_toml_from_catalog(md: &str) -> Result<String> {
    let mut in_toml = false;
    let mut buf = String::new();
    for line in md.lines() {
        let trimmed = line.trim();
        if !in_toml && (trimmed == "```toml" || trimmed == "```TOML") {
            in_toml = true;
            continue;
        }
        if in_toml && trimmed == "```" {
            if buf.trim().is_empty() {
                anyhow::bail!("empty toml fence in catalog");
            }
            return Ok(buf);
        }
        if in_toml {
            buf.push_str(line);
            buf.push('\n');
        }
    }
    anyhow::bail!("no ```toml fence found in catalog markdown")
}

pub fn write_drivers_bundle(
    devices: &[DeviceConfig],
    devices_dir: &Path,
    settings_path: &Path,
    catalog_path: &Path,
    header_extra: &str,
) -> Result<()> {
    if let Some(parent) = devices_dir.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::create_dir_all(devices_dir)?;

    let written: HashMap<u32, String> = devices
        .iter()
        .map(|d| (d.device_instance, device_filename(d)))
        .collect();

    for dev in devices {
        let path = devices_dir.join(device_filename(dev));
        std::fs::write(&path, emit_device_toml(dev, None))
            .with_context(|| format!("writing {}", path.display()))?;
    }

    // Drop renamed leftovers for the same instance (e.g. 5007-old-name.toml → 5007-new-name.toml).
    if devices_dir.is_dir() {
        for entry in std::fs::read_dir(devices_dir)? {
            let path = entry?.path();
            if !path.extension().is_some_and(|x| x == "toml") {
                continue;
            }
            let Some(stem) = path.file_stem().and_then(|s| s.to_str()) else {
                continue;
            };
            let Some(inst) = stem.split('-').next().and_then(|s| s.parse::<u32>().ok()) else {
                continue;
            };
            if let Some(canonical) = written.get(&inst) {
                if path.file_name().and_then(|n| n.to_str()) != Some(canonical.as_str()) {
                    std::fs::remove_file(&path)
                        .with_context(|| format!("removing stale driver {}", path.display()))?;
                }
            }
        }
    }

    if let Some(parent) = settings_path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(settings_path, emit_settings_toml(header_extra))
        .with_context(|| format!("writing {}", settings_path.display()))?;

    let md_text = emit_drivers_catalog_md(devices, header_extra);
    std::fs::write(catalog_path, md_text)
        .with_context(|| format!("writing {}", catalog_path.display()))?;
    Ok(())
}
