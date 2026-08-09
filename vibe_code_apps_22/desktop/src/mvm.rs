//! Measured-vs-modeled + EnergyPlus multi-resolution validation (Wave 5 UX).

use std::fs;
use std::path::PathBuf;

use eframe::egui;
use serde::Deserialize;

/// Canonical physics honesty — filename `*gshp*` is naming only, not plant type.
pub const PHYSICS_LABEL_IDEALLOADS: &str =
    "IdealLoads + fixed-COP electrical proxy (not GSHP/GLHE plant)";

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
}

#[derive(Debug, Clone, Deserialize)]
pub struct ResolutionBlock {
    pub resolution: String,
    pub status: String,
    pub n: u64,
    pub p: u64,
    #[serde(default, deserialize_with = "deserialize_opt_f64")]
    pub nmbe_pct: Option<f64>,
    #[serde(default, deserialize_with = "deserialize_opt_f64")]
    pub cvrmse_pct: Option<f64>,
    #[serde(default)]
    pub labeled_as_gl14: bool,
    #[serde(default)]
    pub partial_year_monthly: bool,
}

#[derive(Debug, Clone, Default, Deserialize)]
pub struct Resolutions {
    /// Legacy alias — prefer monthly_utility when present.
    pub monthly: Option<ResolutionBlock>,
    /// Utility-bill monthly product (never interval aggregates).
    #[serde(default)]
    pub monthly_utility: Option<ResolutionBlock>,
    /// Interval-meter aggregated to monthly (NOT utility bills).
    #[serde(default)]
    pub monthly_interval: Option<ResolutionBlock>,
    pub hourly: Option<ResolutionBlock>,
    pub q15_dsm: Option<ResolutionBlock>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct MultiresOverall {
    pub monthly_pass: bool,
    pub hourly_pass: bool,
    pub recommendation_allowed: bool,
    pub blocker_reason: Option<String>,
    #[serde(default)]
    pub optimizer_ready: bool,
    #[serde(default)]
    pub operational_dsm_readiness: Option<String>,
    #[serde(default = "default_true")]
    pub operational_dsm_prohibited_until_gates_clear: bool,
}

fn default_true() -> bool {
    true
}

#[derive(Debug, Clone, Deserialize)]
pub struct MultiresValidation {
    pub schema: String,
    pub acceptance_policy_id: String,
    pub physics_label: String,
    pub idf_sha256: Option<String>,
    pub epw_sha256: Option<String>,
    pub formula: Option<String>,
    #[serde(default)]
    pub resolutions: Resolutions,
    pub overall: MultiresOverall,
}

#[derive(Debug, Clone)]
pub struct MultiresBundle {
    pub doc: Option<MultiresValidation>,
    pub error: Option<String>,
    pub path: String,
}

/// Runtime inputs that further suppress recommendation language.
#[derive(Debug, Clone, Default)]
pub struct RecommendGateExtras {
    pub smoke_farm: bool,
    pub ood: bool,
    pub comfort_fail: bool,
    pub hash_mismatch: bool,
}

fn candidate_dirs() -> Vec<PathBuf> {
    // Site live reports take precedence over stale local/exe-bundled artifacts.
    let mut out = Vec::new();
    if let Ok(site) = std::env::var("LAKESIDE_SITE_ROOT") {
        let root = PathBuf::from(site);
        out.push(root.join("reports").join("eplus").join("multires"));
        out.push(root.join("reports").join("eplus").join("mvm"));
    }
    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            out.push(dir.join("mvm"));
            out.push(dir.join("artifacts").join("mvm"));
        }
    }
    out.push(
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("artifacts")
            .join("mvm"),
    );
    out
}

pub fn load_mvm_bundle() -> MvmBundle {
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
                };
            }
        }
    }
    MvmBundle {
        summary: None,
        error: Some(
            "Measured-vs-modeled artifacts missing. Run scripts/validate_mvm.py \
             against the site Lakeside staged twin."
                .into(),
        ),
        summary_path: "(not found)".into(),
        overlay_path: None,
        parity_path: None,
        monthly_path: None,
        aligned_csv: None,
    }
}

/// Load `eplus_multires_validation.json` (schema eplus_multires_validation_v1).
/// Missing file is a soft fallback — UI shows unavailable badges, not a hard crash.
pub fn load_multires_validation() -> MultiresBundle {
    for dir in candidate_dirs() {
        let path = dir.join("eplus_multires_validation.json");
        if !path.is_file() {
            continue;
        }
        match fs::read_to_string(&path) {
            Ok(txt) => match parse_multires_json(&txt) {
                Ok(doc) => {
                    if doc.schema != "eplus_multires_validation_v1" {
                        return MultiresBundle {
                            doc: None,
                            error: Some(format!(
                                "Unexpected schema {:?} (want eplus_multires_validation_v1)",
                                doc.schema
                            )),
                            path: path.display().to_string(),
                        };
                    }
                    return MultiresBundle {
                        doc: Some(doc),
                        error: None,
                        path: path.display().to_string(),
                    };
                }
                Err(e) => {
                    return MultiresBundle {
                        doc: None,
                        error: Some(format!("Multi-res validation parse error: {e}")),
                        path: path.display().to_string(),
                    };
                }
            },
            Err(e) => {
                return MultiresBundle {
                    doc: None,
                    error: Some(format!("Multi-res validation read error: {e}")),
                    path: path.display().to_string(),
                };
            }
        }
    }
    MultiresBundle {
        doc: None,
        error: Some(
            "eplus_multires_validation.json missing — run scripts/validate_eplus_multires.py \
             (mirrors into desktop/artifacts/mvm/)."
                .into(),
        ),
        path: "(not found)".into(),
    }
}

/// Python `json.dumps` may emit bare `NaN`; normalize before serde.
pub fn parse_multires_json(raw: &str) -> Result<MultiresValidation, serde_json::Error> {
    let cleaned = sanitize_json_nan(raw);
    serde_json::from_str(&cleaned)
}

fn sanitize_json_nan(raw: &str) -> String {
    // Replace unquoted NaN / Infinity tokens that Python allow_nan emits.
    let mut out = String::with_capacity(raw.len());
    let bytes = raw.as_bytes();
    let mut i = 0;
    while i < bytes.len() {
        if matches_token(bytes, i, b"NaN") {
            out.push_str("null");
            i += 3;
        } else if matches_token(bytes, i, b"Infinity") {
            out.push_str("null");
            i += 8;
        } else if matches_token(bytes, i, b"-Infinity") {
            out.push_str("null");
            i += 9;
        } else {
            out.push(bytes[i] as char);
            i += 1;
        }
    }
    out
}

fn matches_token(bytes: &[u8], i: usize, tok: &[u8]) -> bool {
    if i + tok.len() > bytes.len() {
        return false;
    }
    if &bytes[i..i + tok.len()] != tok {
        return false;
    }
    let before_ok = i == 0 || !bytes[i - 1].is_ascii_alphanumeric();
    let after_i = i + tok.len();
    let after_ok = after_i >= bytes.len() || !bytes[after_i].is_ascii_alphanumeric();
    before_ok && after_ok
}

fn some_if_file(p: PathBuf) -> Option<PathBuf> {
    if p.is_file() {
        Some(p)
    } else {
        None
    }
}

/// Force IdealLoads + fixed-COP wording; never imply GSHP plant from filename.
pub fn display_physics_label(raw: Option<&str>) -> String {
    let s = raw.unwrap_or("").trim();
    if s.is_empty() {
        return PHYSICS_LABEL_IDEALLOADS.into();
    }
    let lower = s.to_ascii_lowercase();
    // Reject labels that claim GSHP without the "not GSHP" honesty clause.
    let claims_gshp = lower.contains("gshp") || lower.contains("glhe");
    let denies_gshp = lower.contains("not gshp")
        || lower.contains("≠ gshp")
        || lower.contains("!= gshp")
        || lower.contains("!=gshp")
        || lower.contains("not a gshp")
        || lower.contains("(not gshp");
    if claims_gshp && !denies_gshp {
        return PHYSICS_LABEL_IDEALLOADS.into();
    }
    if lower.contains("idealloads") || lower.contains("ideal loads") {
        return s.to_string();
    }
    PHYSICS_LABEL_IDEALLOADS.into()
}

/// Whether UI may speak in recommendation language, plus one blocker reason.
pub fn recommendation_language_gate(
    multires: Option<&MultiresValidation>,
    extras: &RecommendGateExtras,
) -> (bool, Option<String>) {
    if extras.hash_mismatch {
        return (false, Some("hash_mismatch".into()));
    }
    if extras.smoke_farm {
        return (false, Some("smoke_farm_screening_only".into()));
    }
    if extras.ood {
        return (false, Some("OUT_OF_DISTRIBUTION".into()));
    }
    if extras.comfort_fail {
        return (false, Some("comfort_fail".into()));
    }
    let Some(doc) = multires else {
        return (false, Some("multires_validation_missing".into()));
    };
    if !doc.overall.recommendation_allowed {
        return (
            false,
            doc.overall
                .blocker_reason
                .clone()
                .or_else(|| Some("gates_not_met".into())),
        );
    }
    if !doc.overall.monthly_pass || !doc.overall.hourly_pass {
        return (false, Some("gates_not_met".into()));
    }
    (true, None)
}

/// Detect IDF hash disagreement between MVM summary and multi-res doc (when both present).
pub fn idf_hash_mismatch(mvm: &MvmBundle, multires: &MultiresBundle) -> bool {
    let a = mvm
        .summary
        .as_ref()
        .and_then(|s| s.idf_sha256.as_deref())
        .map(|h| h.trim().to_ascii_uppercase());
    let b = multires
        .doc
        .as_ref()
        .and_then(|d| d.idf_sha256.as_deref())
        .map(|h| h.trim().to_ascii_uppercase());
    match (a, b) {
        (Some(x), Some(y)) if !x.is_empty() && !y.is_empty() => x != y,
        _ => false,
    }
}

fn status_color(status: &str) -> egui::Color32 {
    match status {
        "pass" => egui::Color32::from_rgb(120, 190, 130),
        "fail" => egui::Color32::from_rgb(230, 100, 90),
        "insufficient_data" => egui::Color32::from_rgb(210, 160, 80),
        "diagnostic_only" | "waived" => egui::Color32::from_rgb(140, 170, 210),
        _ => egui::Color32::from_rgb(160, 160, 170),
    }
}

/// M&V / calibrated-sim plain language for a resolution status code.
pub fn mv_verdict_phrase(status: &str) -> &'static str {
    match status {
        "pass" => "within screen",
        "fail" => "outside screen",
        "insufficient_data" => "insufficient sample",
        "diagnostic_only" => "informational only (not a savings gate)",
        "waived" => "waived",
        _ => "not assessed",
    }
}

fn fmt_pct(v: Option<f64>) -> String {
    match v {
        Some(x) if x.is_finite() => format!("{x:.1}%"),
        _ => "—".into(),
    }
}

/// Typical M&V one-liner: NMBE · CV(RMSE) · n · verdict.
pub fn mv_metric_line(name: &str, block: Option<&ResolutionBlock>) -> (String, egui::Color32) {
    match block {
        Some(b) => {
            let line = format!(
                "{name}: NMBE {nmbe} · CV(RMSE) {cv} · n={n} · {verdict}",
                nmbe = fmt_pct(b.nmbe_pct),
                cv = fmt_pct(b.cvrmse_pct),
                n = b.n,
                verdict = mv_verdict_phrase(&b.status),
            );
            (line, status_color(&b.status))
        }
        None => (
            format!("{name}: not assessed"),
            egui::Color32::from_rgb(140, 140, 150),
        ),
    }
}

/// Operator-facing readiness (avoid "DSM: BLOCKED" / "diagnostic_only" jargon).
pub fn mv_savings_claim_line(doc: Option<&MultiresValidation>) -> (String, egui::Color32) {
    let ready = doc
        .and_then(|d| d.overall.operational_dsm_readiness.as_deref())
        .unwrap_or("BLOCKED");
    if ready.eq_ignore_ascii_case("READY") {
        (
            "Savings claim: eligible for screening language (gates clear)".into(),
            egui::Color32::from_rgb(120, 190, 130),
        )
    } else {
        (
            "Savings claim: not verified — fail-closed (hourly / interval fit outside screen)"
                .into(),
            egui::Color32::from_rgb(230, 120, 90),
        )
    }
}

/// Compact main-screen strip: utility vs interval monthly + hourly + savings claim.
pub fn show_multires_badge_strip(
    ui: &mut egui::Ui,
    bundle: &MultiresBundle,
    extras: &RecommendGateExtras,
) {
    ui.horizontal_wrapped(|ui| {
        ui.strong("M&V screens");
        ui.separator();
        match &bundle.doc {
            Some(doc) => {
                let util = doc
                    .resolutions
                    .monthly_utility
                    .as_ref()
                    .or(doc.resolutions.monthly.as_ref());
                let interv = doc.resolutions.monthly_interval.as_ref();
                let (mu, cmu) = mv_metric_line("Utility bills (mo)", util);
                let (mi, cmi) = mv_metric_line("Interval→month", interv);
                let (h, ch) = mv_metric_line("Hourly kW", doc.resolutions.hourly.as_ref());
                let (q, cq) = mv_metric_line(
                    "15-min shape",
                    doc.resolutions.q15_dsm.as_ref(),
                );
                ui.colored_label(cmu, mu);
                ui.colored_label(cmi, mi);
                ui.colored_label(ch, h);
                ui.colored_label(cq, q);
                let (claim, rc) = mv_savings_claim_line(Some(doc));
                ui.colored_label(rc, claim);
            }
            None => {
                ui.colored_label(
                    egui::Color32::from_rgb(210, 160, 80),
                    "M&V report not loaded · Savings claim: not verified",
                );
            }
        }
    });

    let physics = display_physics_label(bundle.doc.as_ref().map(|d| d.physics_label.as_str()));
    ui.label(
        egui::RichText::new(format!(
            "Model class: {physics} (IdealLoads + fixed-COP ≠ ground-source heat-pump plant)"
        ))
        .italics()
        .color(egui::Color32::from_rgb(200, 170, 120)),
    );

    let (allowed, blocker) = recommendation_language_gate(bundle.doc.as_ref(), extras);
    if allowed {
        ui.colored_label(
            egui::Color32::from_rgb(120, 190, 130),
            "Operator recommendation language: allowed (gates clear)",
        );
    } else {
        ui.colored_label(
            egui::Color32::from_rgb(230, 120, 90),
            format!(
                "Operator recommendation language: withheld · {}",
                blocker
                    .as_deref()
                    .unwrap_or("fit screens not met")
                    .replace('_', " ")
            ),
        );
    }
}

/// Large, centered M&V glance for the tutorial (no jargon badges).
pub fn show_tutorial_mv_glance(ui: &mut egui::Ui, bundle: &MultiresBundle) {
    let title_size = 22.0;
    let body_size = 18.0;
    match &bundle.doc {
        Some(doc) => {
            let util = doc
                .resolutions
                .monthly_utility
                .as_ref()
                .or(doc.resolutions.monthly.as_ref());
            let hourly = doc.resolutions.hourly.as_ref();
            let q15 = doc.resolutions.q15_dsm.as_ref();

            ui.label(
                egui::RichText::new("How close is the model to measured data?")
                    .size(title_size)
                    .strong(),
            );
            ui.add_space(10.0);

            let (u_line, u_c) = mv_metric_line("Utility bills (monthly energy)", util);
            ui.colored_label(u_c, egui::RichText::new(u_line).size(body_size));
            ui.label(
                egui::RichText::new(
                    "Typical monthly screen ≈ |NMBE| ≤ 5% and CV(RMSE) ≤ 15% (partial year).",
                )
                .size(15.0)
                .weak(),
            );
            ui.add_space(8.0);

            let (h_line, h_c) = mv_metric_line("Hourly demand (facility kW)", hourly);
            ui.colored_label(h_c, egui::RichText::new(h_line).size(body_size));
            ui.label(
                egui::RichText::new(
                    "Typical calibrated-sim hourly screen ≈ CV(RMSE) ≤ ~30% — higher means shape/level miss.",
                )
                .size(15.0)
                .weak(),
            );
            ui.add_space(8.0);

            let (q_line, q_c) = mv_metric_line("15-minute demand shape", q15);
            ui.colored_label(q_c, egui::RichText::new(q_line).size(body_size));
            ui.label(
                egui::RichText::new(
                    "15-min is informational for peak timing — not used alone to claim savings.",
                )
                .size(15.0)
                .weak(),
            );
            ui.add_space(12.0);

            let (claim, cc) = mv_savings_claim_line(Some(doc));
            ui.colored_label(cc, egui::RichText::new(claim).size(body_size).strong());
        }
        None => {
            ui.label(
                egui::RichText::new("No multi-resolution M&V report loaded yet.")
                    .size(body_size),
            );
            ui.colored_label(
                egui::Color32::from_rgb(230, 120, 90),
                egui::RichText::new("Savings claim: not verified")
                    .size(body_size)
                    .strong(),
            );
        }
    }
}

/// Detailed Validation tab contents (multi-res metrics + legacy MVM).
pub fn show_validation_tab(ui: &mut egui::Ui, multires: &MultiresBundle, mvm: &MvmBundle) {
    ui.heading("EnergyPlus multi-resolution validation");
    if let Some(err) = &multires.error {
        ui.colored_label(egui::Color32::from_rgb(230, 90, 90), err);
    }
    if let Some(doc) = &multires.doc {
        ui.label(format!("schema: {}", doc.schema));
        ui.label(format!("policy: {}", doc.acceptance_policy_id));
        ui.label(format!(
            "Physics: {}",
            display_physics_label(Some(&doc.physics_label))
        ));
        ui.label(format!("file: {}", multires.path));
        if let Some(f) = &doc.formula {
            ui.weak(f);
        }

        egui::Grid::new("multires_overall")
            .num_columns(2)
            .striped(true)
            .show(ui, |ui| {
                ui.label("monthly_pass");
                ui.label(doc.overall.monthly_pass.to_string());
                ui.end_row();
                ui.label("hourly_pass");
                ui.label(doc.overall.hourly_pass.to_string());
                ui.end_row();
                ui.label("recommendation_allowed");
                ui.label(doc.overall.recommendation_allowed.to_string());
                ui.end_row();
                ui.label("blocker_reason");
                ui.label(
                    doc.overall
                        .blocker_reason
                        .clone()
                        .unwrap_or_else(|| "—".into()),
                );
                ui.end_row();
                ui.label("optimizer_ready");
                ui.label(doc.overall.optimizer_ready.to_string());
                ui.end_row();
                ui.label("operational DSM");
                ui.label(
                    if doc.overall.operational_dsm_prohibited_until_gates_clear {
                        "prohibited until gates clear"
                    } else {
                        "not prohibited"
                    },
                );
                ui.end_row();
                ui.label("IDF SHA-256");
                ui.monospace(doc.idf_sha256.clone().unwrap_or_else(|| "—".into()));
                ui.end_row();
                ui.label("EPW SHA-256");
                ui.monospace(doc.epw_sha256.clone().unwrap_or_else(|| "—".into()));
                ui.end_row();
            });

        ui.separator();
        ui.heading("Resolutions (sources kept separate)");
        for (title, block) in [
            (
                "A. Monthly utility bills (PARTIAL-PERIOD SCREEN)",
                doc.resolutions
                    .monthly_utility
                    .as_ref()
                    .or(doc.resolutions.monthly.as_ref()),
            ),
            (
                "B. Monthly interval-meter reconciliation (NOT utility bills)",
                doc.resolutions.monthly_interval.as_ref(),
            ),
            (
                "C. Hourly demand (calibrated-sim screen)",
                doc.resolutions.hourly.as_ref(),
            ),
            ("D. 15-min DSM diagnostic", doc.resolutions.q15_dsm.as_ref()),
        ] {
            ui.strong(title);
            match block {
                Some(b) => {
                    ui.label(format!(
                        "status={}  n={}  p={}  |NMBE|≈{}%  CVRMSE≈{}%  GL14-label={}",
                        b.status,
                        b.n,
                        b.p,
                        fmt_opt(b.nmbe_pct),
                        fmt_opt(b.cvrmse_pct),
                        b.labeled_as_gl14
                    ));
                    if b.partial_year_monthly || b.n < 12 {
                        ui.weak(
                            "PARTIAL-PERIOD MONTHLY THRESHOLD SCREEN — not unqualified GL14 PASS",
                        );
                    }
                    if b.resolution.contains("15") || title.contains("15-min") {
                        ui.weak("Never marketed as 15-minute GL14.");
                    }
                }
                None => {
                    ui.weak("not present in validation JSON");
                }
            }
        }
    } else {
        ui.weak("Multi-res validation unavailable — badges fall back to unavailable.");
    }

    ui.add_space(10.0);
    ui.separator();
    show_mvm_panel(ui, mvm);
}

fn fmt_opt(v: Option<f64>) -> String {
    match v {
        Some(x) if x.is_finite() => format!("{x:.2}"),
        _ => "—".into(),
    }
}

pub fn show_mvm_panel(ui: &mut egui::Ui, bundle: &MvmBundle) {
    ui.heading("Measured vs modeled (native E+)");
    if let Some(err) = &bundle.error {
        ui.colored_label(egui::Color32::from_rgb(230, 90, 90), err);
        return;
    }
    let Some(s) = &bundle.summary else {
        ui.label("No MVM summary loaded.");
        return;
    };
    ui.label(
        egui::RichText::new(display_physics_label(s.honesty.as_deref()))
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
                s.cvrmse_denominator
                    .clone()
                    .unwrap_or_else(|| "mean_obs".into())
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

fn deserialize_opt_f64<'de, D>(deserializer: D) -> Result<Option<f64>, D::Error>
where
    D: serde::Deserializer<'de>,
{
    let v = Option::<serde_json::Value>::deserialize(deserializer)?;
    Ok(match v {
        None | Some(serde_json::Value::Null) => None,
        Some(serde_json::Value::Number(n)) => n.as_f64().filter(|x| x.is_finite()),
        Some(serde_json::Value::String(s)) => {
            let t = s.trim();
            if t.eq_ignore_ascii_case("nan")
                || t.eq_ignore_ascii_case("inf")
                || t.eq_ignore_ascii_case("-inf")
                || t.eq_ignore_ascii_case("infinity")
                || t.eq_ignore_ascii_case("-infinity")
            {
                None
            } else {
                t.parse::<f64>().ok().filter(|x| x.is_finite())
            }
        }
        _ => None,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    const SAMPLE_FAIL: &str = r#"{
        "schema": "eplus_multires_validation_v1",
        "acceptance_policy_id": "eplus_dsm_acceptance_policy_v1",
        "physics_label": "IdealLoads + fixed-COP electrical proxy (not GSHP/GLHE plant)",
        "idf_sha256": "AAA",
        "epw_sha256": "BBB",
        "formula": "NREL / older G14 practice",
        "resolutions": {
            "monthly": {
                "resolution": "monthly",
                "status": "pass",
                "n": 11,
                "p": 1,
                "nmbe_pct": 2.7,
                "cvrmse_pct": 11.5,
                "mean_obs": 100.0,
                "labeled_as_gl14": true,
                "partial_year_monthly": true
            },
            "hourly": {
                "resolution": "hourly",
                "status": "fail",
                "n": 8000,
                "p": 1,
                "nmbe_pct": 3.1,
                "cvrmse_pct": 97.0,
                "mean_obs": 50.0,
                "labeled_as_gl14": false,
                "partial_year_monthly": false
            },
            "q15_dsm": {
                "resolution": "15min",
                "status": "diagnostic_only",
                "n": 0,
                "p": 1,
                "nmbe_pct": null,
                "cvrmse_pct": null,
                "labeled_as_gl14": false,
                "partial_year_monthly": false
            }
        },
        "overall": {
            "monthly_pass": true,
            "hourly_pass": false,
            "recommendation_allowed": false,
            "blocker_reason": "hourly=fail",
            "optimizer_ready": false,
            "operational_dsm_prohibited_until_gates_clear": true
        }
    }"#;

    #[test]
    fn parses_multires_schema_v1() {
        let doc = parse_multires_json(SAMPLE_FAIL).unwrap();
        assert_eq!(doc.schema, "eplus_multires_validation_v1");
        assert!(doc.overall.monthly_pass);
        assert!(!doc.overall.hourly_pass);
        assert!(!doc.overall.recommendation_allowed);
        assert_eq!(doc.overall.blocker_reason.as_deref(), Some("hourly=fail"));
        assert_eq!(doc.resolutions.hourly.as_ref().unwrap().status, "fail");
        assert_eq!(
            doc.resolutions.q15_dsm.as_ref().unwrap().status,
            "diagnostic_only"
        );
    }

    #[test]
    fn sanitizes_python_nan_tokens() {
        let raw = r#"{
            "schema": "eplus_multires_validation_v1",
            "acceptance_policy_id": "p",
            "physics_label": "IdealLoads + fixed-COP (not GSHP)",
            "resolutions": {
                "monthly": {
                    "resolution": "monthly",
                    "status": "insufficient_data",
                    "n": 0,
                    "p": 1,
                    "nmbe_pct": NaN,
                    "cvrmse_pct": NaN,
                    "labeled_as_gl14": true
                }
            },
            "overall": {
                "monthly_pass": false,
                "hourly_pass": false,
                "recommendation_allowed": false,
                "blocker_reason": "incomplete",
                "optimizer_ready": false,
                "operational_dsm_prohibited_until_gates_clear": true
            }
        }"#;
        let doc = parse_multires_json(raw).unwrap();
        assert!(doc.resolutions.monthly.as_ref().unwrap().nmbe_pct.is_none());
    }

    #[test]
    fn physics_label_rejects_bare_gshp_claim() {
        assert!(display_physics_label(Some("GSHP plant twin")).contains("IdealLoads"));
        assert!(
            display_physics_label(Some("IdealLoads + fixed-COP (not GSHP/GLHE)"))
                .contains("IdealLoads")
        );
        assert_eq!(display_physics_label(None), PHYSICS_LABEL_IDEALLOADS);
    }

    #[test]
    fn recommendation_gate_blocks_smoke_ood_comfort_hash() {
        let doc = parse_multires_json(SAMPLE_FAIL).unwrap();
        // Even if we forged recommendation_allowed, extras still block.
        let mut ok = doc.clone();
        ok.overall.recommendation_allowed = true;
        ok.overall.monthly_pass = true;
        ok.overall.hourly_pass = true;
        ok.overall.blocker_reason = None;

        let (a, r) = recommendation_language_gate(
            Some(&ok),
            &RecommendGateExtras {
                smoke_farm: true,
                ..Default::default()
            },
        );
        assert!(!a);
        assert_eq!(r.as_deref(), Some("smoke_farm_screening_only"));

        let (a, r) = recommendation_language_gate(
            Some(&ok),
            &RecommendGateExtras {
                ood: true,
                ..Default::default()
            },
        );
        assert!(!a);
        assert_eq!(r.as_deref(), Some("OUT_OF_DISTRIBUTION"));

        let (a, r) = recommendation_language_gate(
            Some(&ok),
            &RecommendGateExtras {
                comfort_fail: true,
                ..Default::default()
            },
        );
        assert!(!a);
        assert_eq!(r.as_deref(), Some("comfort_fail"));

        let (a, r) = recommendation_language_gate(
            Some(&ok),
            &RecommendGateExtras {
                hash_mismatch: true,
                ..Default::default()
            },
        );
        assert!(!a);
        assert_eq!(r.as_deref(), Some("hash_mismatch"));

        let (a, r) = recommendation_language_gate(Some(&doc), &RecommendGateExtras::default());
        assert!(!a);
        assert_eq!(r.as_deref(), Some("hourly=fail"));

        let (a, r) = recommendation_language_gate(None, &RecommendGateExtras::default());
        assert!(!a);
        assert_eq!(r.as_deref(), Some("multires_validation_missing"));
    }

    #[test]
    fn missing_file_is_graceful_bundle() {
        // load_multires_validation may or may not find a file in CI; ensure type compiles
        // and missing path message is non-empty when absent.
        let b = MultiresBundle {
            doc: None,
            error: Some("missing".into()),
            path: "(not found)".into(),
        };
        assert!(b.doc.is_none());
        assert!(b.error.is_some());
    }
}
