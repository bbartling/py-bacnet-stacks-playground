//! Measured-vs-modeled provenance panel (loads bundled JSON/CSV/PNG artifacts).

use std::fs;
use std::path::PathBuf;

use eframe::egui;
use serde::Deserialize;

#[derive(Debug, Clone, Default, Deserialize)]
pub struct MvmSummary {
    pub honesty: Option<String>,
    pub n_hourly: Option<usize>,
    pub hourly_mae_kw: Option<f64>,
    pub hourly_rmse_kw: Option<f64>,
    pub hourly_mbe_kw: Option<f64>,
    pub hourly_nmbe_pct: Option<f64>,
    pub hourly_cvrmse_pct: Option<f64>,
    pub cvrmse_denominator: Option<String>,
    pub idf_sha256: Option<String>,
    pub epw_sha256: Option<String>,
    pub heat_cop: Option<f64>,
    pub cool_cop: Option<f64>,
    pub time_span_utc: Option<Vec<Option<String>>>,
    pub alignment_policy: Option<serde_json::Value>,
    pub monthly_utility_gl14: Option<serde_json::Value>,
    pub missingness_note: Option<String>,
}

#[derive(Debug, Clone)]
pub struct MvmBundle {
    pub summary: Option<MvmSummary>,
    pub error: Option<String>,
    pub summary_path: String,
    pub overlay_path: Option<PathBuf>,
    pub parity_path: Option<PathBuf>,
    pub monthly_path: Option<PathBuf>,
    pub aligned_csv: Option<PathBuf>,
    pub demo_mode: bool,
}

fn candidate_dirs() -> Vec<PathBuf> {
    let mut out = Vec::new();
    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            out.push(dir.join("mvm"));
            out.push(dir.join("artifacts").join("mvm"));
        }
    }
    out.push(PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("artifacts").join("mvm"));
    if let Ok(site) = std::env::var("LAKESIDE_SITE_ROOT") {
        out.push(PathBuf::from(site).join("reports").join("eplus").join("mvm"));
    }
    out
}

pub fn load_mvm_bundle() -> MvmBundle {
    let demo = std::env::var("LAKESIDE_DEMO_NOT_ENERGYPLUS")
        .map(|v| matches!(v.to_ascii_lowercase().as_str(), "1" | "true" | "yes"))
        .unwrap_or(false);

    for dir in candidate_dirs() {
        let sum = dir.join("mvm_summary.json");
        if !sum.is_file() {
            continue;
        }
        match fs::read_to_string(&sum) {
            Ok(txt) => match serde_json::from_str::<MvmSummary>(&txt) {
                Ok(s) => {
                    return MvmBundle {
                        summary: Some(s),
                        error: None,
                        summary_path: sum.display().to_string(),
                        overlay_path: some_if_file(dir.join("mvm_hourly_overlay.png")),
                        parity_path: some_if_file(dir.join("mvm_parity.png")),
                        monthly_path: some_if_file(dir.join("mvm_monthly_gl14.png")),
                        aligned_csv: some_if_file(dir.join("aligned_hourly_kw.csv")),
                        demo_mode: demo,
                    };
                }
                Err(e) => {
                    return MvmBundle {
                        summary: None,
                        error: Some(format!("MVM JSON parse error: {e}")),
                        summary_path: sum.display().to_string(),
                        overlay_path: None,
                        parity_path: None,
                        monthly_path: None,
                        aligned_csv: None,
                        demo_mode: demo,
                    };
                }
            },
            Err(e) => {
                return MvmBundle {
                    summary: None,
                    error: Some(format!("MVM read error: {e}")),
                    summary_path: sum.display().to_string(),
                    overlay_path: None,
                    parity_path: None,
                    monthly_path: None,
                    aligned_csv: None,
                    demo_mode: demo,
                };
            }
        }
    }
    MvmBundle {
        summary: None,
        error: Some(
            "Measured-vs-modeled artifacts missing. Run scripts/validate_mvm.py \
             (or set LAKESIDE_DEMO_NOT_ENERGYPLUS=1 only for DEMO)."
                .into(),
        ),
        summary_path: "(not found)".into(),
        overlay_path: None,
        parity_path: None,
        monthly_path: None,
        aligned_csv: None,
        demo_mode: demo,
    }
}

fn some_if_file(p: PathBuf) -> Option<PathBuf> {
    if p.is_file() {
        Some(p)
    } else {
        None
    }
}

pub fn show_mvm_panel(ui: &mut egui::Ui, bundle: &MvmBundle) {
    ui.heading("Measured vs modeled (native E+)");
    if bundle.demo_mode {
        ui.colored_label(
            egui::Color32::from_rgb(220, 120, 80),
            "DEMO / NOT ENERGYPLUS mode — do not treat as production validation",
        );
    }
    if let Some(err) = &bundle.error {
        ui.colored_label(egui::Color32::from_rgb(230, 90, 90), err);
        return;
    }
    let Some(s) = &bundle.summary else {
        ui.label("No MVM summary loaded.");
        return;
    };
    ui.label(
        egui::RichText::new(
            s.honesty
                .clone()
                .unwrap_or_else(|| "Ideal Loads + fixed-COP proxy".into()),
        )
        .italics()
        .color(egui::Color32::from_rgb(200, 170, 120)),
    );
    egui::Grid::new("mvm_prov")
        .num_columns(2)
        .striped(true)
        .show(ui, |ui| {
            ui.label("IDF SHA-256");
            ui.monospace(s.idf_sha256.clone().unwrap_or_else(|| "—".into()));
            ui.end_row();
            ui.label("EPW SHA-256");
            ui.monospace(s.epw_sha256.clone().unwrap_or_else(|| "—".into()));
            ui.end_row();
            ui.label("COP heat / cool");
            ui.label(format!(
                "{:.1} / {:.1}",
                s.heat_cop.unwrap_or(3.5),
                s.cool_cop.unwrap_or(4.5)
            ));
            ui.end_row();
            ui.label("n hourly");
            ui.label(format!("{}", s.n_hourly.unwrap_or(0)));
            ui.end_row();
            ui.label("MAE / RMSE (kW)");
            ui.strong(format!(
                "{:.1} / {:.1}",
                s.hourly_mae_kw.unwrap_or(f64::NAN),
                s.hourly_rmse_kw.unwrap_or(f64::NAN)
            ));
            ui.end_row();
            ui.label("MBE / NMBE");
            ui.label(format!(
                "{:.1} kW / {:.2}%",
                s.hourly_mbe_kw.unwrap_or(f64::NAN),
                s.hourly_nmbe_pct.unwrap_or(f64::NAN)
            ));
            ui.end_row();
            ui.label("CVRMSE");
            ui.label(format!(
                "{:.1}% (denom={})",
                s.hourly_cvrmse_pct.unwrap_or(f64::NAN),
                s.cvrmse_denominator.clone().unwrap_or_else(|| "mean_obs".into())
            ));
            ui.end_row();
        });

    ui.separator();
    ui.heading("Monthly utility GL14 (separate)");
    if let Some(m) = &s.monthly_utility_gl14 {
        ui.monospace(serde_json::to_string_pretty(m).unwrap_or_default());
    } else {
        ui.weak("No monthly GL14 block in summary.");
    }

    ui.separator();
    ui.label(format!("Artifacts: {}", bundle.summary_path));
    if let Some(p) = &bundle.aligned_csv {
        ui.label(format!("Aligned CSV: {}", p.display()));
    }
    for (label, path) in [
        ("Hourly overlay", &bundle.overlay_path),
        ("Parity", &bundle.parity_path),
        ("Monthly GL14", &bundle.monthly_path),
    ] {
        if let Some(p) = path {
            ui.label(format!("{label} PNG: {}", p.display()));
        }
    }
    if let Some(note) = &s.missingness_note {
        ui.weak(note);
    }
}
