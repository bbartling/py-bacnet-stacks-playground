//! Hybrid 96-step DSM walk panel — loads versioned JSON contract results.
//!
//! Fail-closed without hybrid artifacts (real baseline + E+ delta walk JSON).
//! Honesty: HYBRID_SCREENING until field DSM trials.

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

#[derive(Debug, Clone, Deserialize)]
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
            let txt = std::fs::read_to_string(&p)
                .with_context(|| format!("read {}", p.display()))?;
            let walk: HybridWalk = serde_json::from_str(&txt).context("parse hybrid walk JSON")?;
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
    ui.label(format!("contract: {}", walk.contract_version));
    ui.label(format!("honesty: {}", walk.honesty));
    ui.label(format!("source: {}", path.display()));
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
    ui.label(format!("Comfort violations (15-min): {}", s.comfort_violations));

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
