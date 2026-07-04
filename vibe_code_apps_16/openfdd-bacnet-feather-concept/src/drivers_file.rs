//! AI / human editable BAS driver list (`config/drivers.toml`).
//!
//! Produced by `bas_scan`, consumed by `bacnet_app` (overrides `poller.devices`
//! in `config.toml` when present).

use std::collections::HashMap;
use std::path::Path;

use anyhow::{Context, Result};
use serde::Deserialize;

use crate::app_config::{DeviceConfig, DevicePointConfig};

/// On-disk drivers file (top-level `[[devices]]`).
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

    /// Prefer `config/drivers.toml` when non-empty; else keep `fallback`.
    pub fn load_devices_or(fallback: Vec<DeviceConfig>, path: &Path) -> Vec<DeviceConfig> {
        if !path.is_file() {
            return fallback;
        }
        match Self::load(path) {
            Ok(file) if !file.devices.is_empty() => {
                tracing::info!(
                    "loaded {} device driver(s) from {}",
                    file.devices.len(),
                    path.display()
                );
                file.devices
            }
            Ok(_) => {
                tracing::warn!(
                    "{} has no devices — using config.toml / defaults",
                    path.display()
                );
                fallback
            }
            Err(err) => {
                tracing::warn!(
                    "could not load {} ({err:#}) — using config.toml / defaults",
                    path.display()
                );
                fallback
            }
        }
    }
}

/// Preserve `enabled=false` (and critical/interval/offset) from a previous drivers file.
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

/// Emit a comment-rich TOML drivers file (easy for humans and AI agents to edit).
pub fn emit_drivers_toml(devices: &[DeviceConfig], header_extra: &str) -> String {
    let mut out = String::new();
    out.push_str("# =============================================================================\n");
    out.push_str("# Open-FDD BAS drivers — AI / human editable poll list\n");
    out.push_str("# =============================================================================\n");
    out.push_str("# HOW TO EDIT (ChatGPT, Cursor, or a text editor):\n");
    out.push_str("#   1. Set enabled = false on any device or point you do NOT want polled\n");
    out.push_str("#   2. Optionally rename point_name for clearer Feather columns\n");
    out.push_str("#   3. Set critical = true on the device that feeds APP-FAULT / duct clone\n");
    out.push_str("#   4. Save this file and restart: cargo run --release --bin bacnet_app\n");
    out.push_str("#\n");
    out.push_str("# Re-scan the BAS (preserves enabled=false when using --merge):\n");
    out.push_str("#   cargo run --release --bin bas_scan -- --low 1 --high 4194302 --ephemeral --merge\n");
    out.push_str("#\n");
    out.push_str("# Companion catalog (tables + same TOML): config/drivers.catalog.md\n");
    out.push_str("# All readings append to a single data/feather_store/telemetry.feather\n");
    if !header_extra.is_empty() {
        out.push_str("#\n");
        for line in header_extra.lines() {
            out.push_str("# ");
            out.push_str(line);
            out.push('\n');
        }
    }
    out.push_str("# =============================================================================\n\n");

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
        out.push('\n');
    }
    out
}

/// Markdown catalog for pasting into ChatGPT / agents.
pub fn emit_drivers_catalog_md(devices: &[DeviceConfig], header_extra: &str) -> String {
    let mut out = String::new();
    out.push_str("# BAS driver catalog (AI / human editable)\n\n");
    out.push_str("Paste this file into ChatGPT or Cursor and ask:\n");
    out.push_str("> Keep only the points we need for FDD / trending; set `enabled = false` on the rest.\n\n");
    out.push_str("## Workflow\n\n");
    out.push_str("1. Edit the TOML block at the bottom (or the summary tables).\n");
    out.push_str("2. Save as `config/drivers.catalog.md`.\n");
    out.push_str("3. Apply: `cargo run --release --bin bas_scan -- --apply-catalog config/drivers.catalog.md`\n");
    out.push_str("4. Restart the app: `cargo run --release --bin bacnet_app`\n\n");
    out.push_str("Or edit `config/drivers.toml` directly — it is the live source of truth.\n\n");
    if !header_extra.is_empty() {
        out.push_str("## Scan metadata\n\n```\n");
        out.push_str(header_extra);
        out.push_str("\n```\n\n");
    }

    out.push_str("## Device summary\n\n");
    out.push_str("| enabled | name | instance | host | routed | points (enabled/total) |\n");
    out.push_str("| --- | --- | ---: | --- | --- | ---: |\n");
    for d in devices {
        let en = d.points.iter().filter(|p| p.enabled).count();
        let routed = if d.mstp_mac.is_some() { "yes" } else { "no" };
        out.push_str(&format!(
            "| {} | {} | {} | {}:{} | {routed} | {en}/{} |\n",
            d.enabled,
            d.name,
            d.device_instance,
            d.host,
            d.port,
            d.points.len()
        ));
    }
    out.push('\n');

    for d in devices {
        out.push_str(&format!(
            "## Device `{}` (instance {})\n\n",
            d.name, d.device_instance
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

    out.push_str("## Full drivers.toml (apply this block)\n\n");
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
    drivers_path: &Path,
    catalog_path: &Path,
    header_extra: &str,
) -> Result<()> {
    if let Some(parent) = drivers_path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let toml_text = emit_drivers_toml(devices, header_extra);
    std::fs::write(drivers_path, toml_text)
        .with_context(|| format!("writing {}", drivers_path.display()))?;
    let md_text = emit_drivers_catalog_md(devices, header_extra);
    std::fs::write(catalog_path, md_text)
        .with_context(|| format!("writing {}", catalog_path.display()))?;
    Ok(())
}
