//! Hybrid 96-step DSM walk panel — loads versioned JSON contract results.
//!
//! Fail-closed without hybrid artifacts (real baseline + E+ delta walk JSON).
//! Honesty: HYBRID_SCREENING until field DSM trials.

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use anyhow::{bail, Context, Result};
use eframe::egui;
use egui_plot::{Line, Plot, PlotPoints};
use serde::Deserialize;

#[derive(Debug, Clone, Deserialize)]
pub struct HybridSummary {
    pub cumulative_kwh_baseline: f64,
    pub cumulative_kwh_hybrid: f64,
    pub peak_kw_baseline: f64,
    pub peak_kw_hybrid: f64,
    #[serde(default)]
    pub peak_step_baseline: i64,
    #[serde(default)]
    pub peak_step_hybrid: i64,
    #[serde(default)]
    pub comfort_violations: i64,
    #[serde(default)]
    pub delta_peak_kw: f64,
    #[serde(default)]
    pub delta_kwh: f64,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct HybridStep {
    pub step_15: i64,
    pub baseline_facility_kw: f64,
    pub hybrid_facility_kw: f64,
    #[serde(default)]
    pub delta_facility_kw: f64,
    #[serde(default)]
    pub cumulative_kwh_baseline: f64,
    #[serde(default)]
    pub cumulative_kwh_hybrid: f64,
    #[serde(default)]
    pub comfort_violations_cum: i64,
    #[serde(default)]
    pub baseline_zone_temps_f: BTreeMap<String, f64>,
    #[serde(default)]
    pub delta_zone_temps_f: BTreeMap<String, f64>,
    #[serde(default)]
    pub hybrid_zone_temps_f: BTreeMap<String, f64>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct HybridWalk {
    pub contract_version: String,
    #[serde(default)]
    pub honesty: String,
    pub steps: Vec<HybridStep>,
    pub summary: HybridSummary,
    #[serde(default)]
    pub champion_baseline: Option<String>,
    #[serde(default)]
    pub champion_delta: Option<String>,
    #[serde(default)]
    pub outcome_flag: Option<String>,
    #[serde(default)]
    pub source: Option<String>,
    #[serde(default)]
    pub weather_mode: Option<String>,
    #[serde(default)]
    pub comfort_htg_sp_f: Option<f64>,
    #[serde(default)]
    pub comfort_band_f: Option<f64>,
    #[serde(default)]
    pub ship_watermark: Option<String>,
}

pub fn default_hybrid_walk_paths() -> Vec<PathBuf> {
    let mut out = Vec::new();
    if let Some(dir) = std::env::var_os("LAKESIDE_ONNX_DIR") {
        out.push(PathBuf::from(dir).join("hybrid_dsm_96_v1_walk.json"));
    }
    if let Ok(exe) = std::env::current_exe() {
        if let Some(d) = exe.parent() {
            out.push(d.join("hybrid_dsm_96_v1_walk.json"));
        }
    }
    if let Some(manifest) = option_env!("CARGO_MANIFEST_DIR") {
        let m = Path::new(manifest);
        out.push(m.join("artifacts").join("hybrid_dsm_96_v1_walk.json"));
        out.push(
            m.join("..")
                .join("ml")
                .join("artifacts")
                .join("fixtures")
                .join("hybrid_dsm_96_v1_walk.json"),
        );
        out.push(
            m.join("..")
                .join("ml")
                .join("artifacts")
                .join("hybrid_dsm_96_v1_walk.json"),
        );
    }
    out.push(PathBuf::from("ml/artifacts/hybrid_dsm_96_v1_walk.json"));
    out
}

pub fn load_hybrid_walk() -> Result<(HybridWalk, PathBuf)> {
    let mut tried = Vec::new();
    for p in default_hybrid_walk_paths() {
        tried.push(p.display().to_string());
        if p.is_file() {
            let txt =
                std::fs::read_to_string(&p).with_context(|| format!("read {}", p.display()))?;
            let mut walk: HybridWalk =
                serde_json::from_str(&txt).context("parse hybrid walk JSON")?;
            if walk.source.is_none() {
                walk.source = Some("precomputed_ship_walk".into());
            }
            if walk.steps.len() != 96 {
                bail!(
                    "hybrid walk must have 96 steps, got {} ({})",
                    walk.steps.len(),
                    p.display()
                );
            }
            if !walk.honesty.is_empty() && walk.honesty != "HYBRID_SCREENING" {
                // still allow, but prefer honesty stamp
            }
            return Ok((walk, p));
        }
    }
    bail!(
        "hybrid walk missing — run Python hybrid rollout / promote_hybrid_ship.py. Tried: {}",
        tried.join(" | ")
    )
}

pub fn show_hybrid_panel(ui: &mut egui::Ui, walk: &HybridWalk, path: &Path) {
    ui.heading("Hybrid 96-step (real baseline + E+ delta)");
    let src = walk
        .source
        .as_deref()
        .unwrap_or(if path.as_os_str().is_empty() {
            "live_onnx"
        } else {
            "precomputed_ship_walk"
        });
    ui.label(format!("source: {src}"));
    ui.label(format!("contract: {}", walk.contract_version));
    ui.label(format!("honesty: {}", walk.honesty));
    if !path.as_os_str().is_empty() {
        ui.label(format!("file: {}", path.display()));
    }
    ui.colored_label(
        egui::Color32::from_rgb(210, 150, 70),
        "IdealLoads + fixed-COP screening twin — not GSHP plant / not operational DSM (filename gshp is naming only).",
    );
    if let Some(flag) = &walk.outcome_flag {
        ui.colored_label(
            egui::Color32::from_rgb(230, 100, 80),
            format!("outcome_flag: {flag} — not a recommended DSM strategy"),
        );
    }
    if let Some(b) = &walk.champion_baseline {
        ui.label(format!("baseline champion: {b}"));
    }
    if let Some(d) = &walk.champion_delta {
        ui.label(format!("delta champion: {d}"));
    }
    ui.separator();
    let s = &walk.summary;
    ui.label(format!(
        "Peak kW  baseline {:.1} → hybrid {:.1}   Δ {:.1}",
        s.peak_kw_baseline, s.peak_kw_hybrid, s.delta_peak_kw
    ));
    ui.label(format!(
        "Energy kWh  baseline {:.1} → hybrid {:.1}   Δ {:.1}",
        s.cumulative_kwh_baseline, s.cumulative_kwh_hybrid, s.delta_kwh
    ));
    ui.label(format!(
        "Comfort violations (15-min): {}",
        s.comfort_violations
    ));

    let base: PlotPoints = walk
        .steps
        .iter()
        .map(|st| [st.step_15 as f64 / 4.0, st.baseline_facility_kw])
        .collect();
    let hyb: PlotPoints = walk
        .steps
        .iter()
        .map(|st| [st.step_15 as f64 / 4.0, st.hybrid_facility_kw])
        .collect();
    Plot::new("hybrid_kw")
        .height(220.0)
        .legend(egui_plot::Legend::default())
        .show(ui, |plot_ui| {
            plot_ui.line(Line::new(base).name("baseline"));
            plot_ui.line(Line::new(hyb).name("hybrid DSM"));
        });

    // Zone trajectories + comfort band (when present on live/regen walks)
    let zone_keys: Vec<String> = walk
        .steps
        .first()
        .map(|s| s.hybrid_zone_temps_f.keys().cloned().collect())
        .unwrap_or_default();
    if !zone_keys.is_empty() {
        ui.separator();
        ui.label("Zone temps (°F) — hybrid + comfort band");
        let sp = walk.comfort_htg_sp_f.unwrap_or(68.0);
        let band = walk.comfort_band_f.unwrap_or(2.0);
        let lo = sp - band;
        Plot::new("hybrid_zones")
            .height(200.0)
            .legend(egui_plot::Legend::default())
            .show(ui, |plot_ui| {
                for zk in &zone_keys {
                    let pts: PlotPoints = walk
                        .steps
                        .iter()
                        .filter_map(|st| {
                            st.hybrid_zone_temps_f
                                .get(zk)
                                .map(|t| [st.step_15 as f64 / 4.0, *t])
                        })
                        .collect();
                    plot_ui.line(Line::new(pts).name(zk.clone()));
                }
                let lo_line: PlotPoints = (0..96).map(|i| [i as f64 / 4.0, lo]).collect();
                plot_ui.line(Line::new(lo_line).name("comfort_lo"));
            });
    }
    if let Some(wm) = &walk.weather_mode {
        ui.label(format!("weather_mode: {wm}"));
    }
    if let Some(w) = &walk.ship_watermark {
        ui.colored_label(
            egui::Color32::from_rgb(230, 120, 40),
            format!("ship watermark: {w}"),
        );
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hybrid_walk_loads_from_desktop_artifacts() {
        let (walk, path) = load_hybrid_walk().expect("hybrid walk must exist for ship");
        assert_eq!(walk.steps.len(), 96);
        assert!(path.is_file());
        assert_eq!(walk.honesty, "HYBRID_SCREENING");
    }
}
