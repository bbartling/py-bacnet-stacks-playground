//! Lakeside heating DSM desktop walk — egui + ONNX.
//!
//! Portable TOD + dual-demand tariff (Creekside CP-2 defaults prefilled).
//! Dual walks: HVAC 24/7 vs DSM strategy → Δpeak / ΔkWh + annual rollup.

mod annual;
mod bills;
mod features;
mod model;
mod mvm;
mod tariff;

use annual::{rollup_annual_savings, AnnualRollup, MonthlyBook};
use bills::{try_autoload_bills, BillBook, DerivedRates};
use eframe::egui;
use egui_plot::{Bar, BarChart, Line, Plot, PlotPoints};
use features::{
    build_features, default_occ_frac, HourInputs, StrategyKnobs, STRATEGY_IDS, ZONE_LABELS,
};
use model::{default_artifact_paths, OnnxModel};
use mvm::{load_mvm_bundle, show_mvm_panel, MvmBundle};
use tariff::{cost_day_tod, creekside_cp2_defaults, DemandTariff, TodDayCost};

fn apply_theme(ctx: &egui::Context) {
    let mut visuals = egui::Visuals::dark();
    visuals.window_fill = egui::Color32::from_rgb(22, 28, 34);
    visuals.panel_fill = egui::Color32::from_rgb(28, 35, 42);
    visuals.extreme_bg_color = egui::Color32::from_rgb(18, 22, 28);
    visuals.widgets.noninteractive.bg_fill = egui::Color32::from_rgb(34, 42, 50);
    visuals.widgets.inactive.bg_fill = egui::Color32::from_rgb(42, 52, 62);
    visuals.widgets.hovered.bg_fill = egui::Color32::from_rgb(55, 68, 80);
    visuals.widgets.active.bg_fill = egui::Color32::from_rgb(70, 88, 104);
    visuals.selection.bg_fill = egui::Color32::from_rgb(196, 110, 48);
    visuals.hyperlink_color = egui::Color32::from_rgb(232, 168, 96);
    visuals.override_text_color = Some(egui::Color32::from_rgb(232, 236, 240));
    ctx.set_visuals(visuals);
    ctx.style_mut(|style| {
        style.spacing.item_spacing = egui::vec2(8.0, 6.0);
        style.spacing.button_padding = egui::vec2(12.0, 6.0);
    });
}

fn main() -> eframe::Result<()> {
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([1360.0, 920.0])
            .with_title("Lakeside Heating DSM — portable tariff + ONNX walk"),
        ..Default::default()
    };
    eframe::run_native(
        "Lakeside Heating DSM",
        options,
        Box::new(|cc| Ok(Box::new(DsmApp::new(cc)))),
    )
}

struct DsmApp {
    model: Option<OnnxModel>,
    load_error: Option<String>,
    honesty: String,
    training_source: String,
    model_banner: String,
    onnx_path_display: String,
    model_name: String,
    metrics_lines: Vec<String>,
    param_rows: Vec<(String, String)>,
    precision_pm: f32,
    precision_note: String,

    month: f32,
    doy: f32,
    is_weekend: bool,
    oat_midnight_f: f32,
    oat_amplitude_f: f32,
    oat_manual: [f32; 24],
    use_manual_oat: bool,
    midnight_zone_f: [f32; 6],

    strategy_idx: usize,
    hp_on: [[bool; 6]; 24],
    use_strategy_occ: bool,
    occ_override: [[f32; 6]; 24],

    /// Legacy flat rates (still editable; used when TOD off)
    energy_rate_per_kwh: f32,
    demand_rate_per_kw: f32,
    similar_days_per_year: f32,
    rate_label: String,
    rate_honesty: String,
    use_tod_tariff: bool,
    tariff: DemandTariff,

    bill_book: Option<BillBook>,
    bill_error: Option<String>,
    bill_warnings: Vec<String>,
    rate_preset_idx: usize,

    monthly_book: Option<MonthlyBook>,
    monthly_error: Option<String>,
    on_peak_energy_share: f32,
    ratchet_tol_kw: f32,

    // Dual walk results
    pred_kw_compare: [f32; 24],
    pred_kw_dsm: [f32; 24],
    compare_label: String,
    dsm_label: String,
    cost_compare: Option<TodDayCost>,
    cost_dsm: Option<TodDayCost>,
    annual: Option<AnnualRollup>,
    mvm: MvmBundle,
    status: String,
}

impl DsmApp {
    fn new(cc: &eframe::CreationContext<'_>) -> Self {
        apply_theme(&cc.egui_ctx);
        let (onnx, meta) = default_artifact_paths();
        let onnx_path_display = onnx.display().to_string();
        let (
            model,
            load_error,
            honesty,
            training_source,
            model_banner,
            model_name,
            metrics_lines,
            param_rows,
            precision_pm,
            precision_note,
        ) = match OnnxModel::load(&onnx, &meta) {
            Ok(m) => {
                let h = m
                    .meta
                    .honesty
                    .clone()
                    .unwrap_or_else(|| "CANDIDATE model".into());
                let s = m
                    .meta
                    .training_source
                    .clone()
                    .unwrap_or_else(|| "unknown".into());
                let banner = m.meta.banner_line();
                let name = m.meta.display_name();
                let metrics = m.meta.metrics_lines();
                let params = m.meta.params_sorted();
                let pm = m.meta.precision_pm();
                let note = m
                    .meta
                    .precision_note
                    .clone()
                    .unwrap_or_else(|| "± = peak MAE screening band".into());
                (Some(m), None, h, s, banner, name, metrics, params, pm, note)
            }
            Err(e) => (
                None,
                Some(format!(
                    "Failed to load ONNX from {} / {}: {e:#}",
                    onnx.display(),
                    meta.display()
                )),
                String::new(),
                String::new(),
                "no model loaded".into(),
                "—".into(),
                Vec::new(),
                Vec::new(),
                0.0,
                String::new(),
            ),
        };

        let mut oat = [0.0_f32; 24];
        for h in 0..24 {
            oat[h] = 18.0 + 8.0 * ((h as f32 - 14.0) * std::f32::consts::PI / 12.0).sin();
        }

        let mut hp_on = [[false; 6]; 24];
        let mut occ = [[0.0_f32; 6]; 24];
        for h in 0..24 {
            let o = default_occ_frac(h, "stagger_preheat", false);
            occ[h] = o;
            for z in 0..6 {
                hp_on[h][z] = o[z] > 0.05;
            }
        }

        let tariff = creekside_cp2_defaults();
        let mut app = Self {
            model,
            load_error,
            honesty,
            training_source,
            model_banner,
            onnx_path_display,
            model_name,
            metrics_lines,
            param_rows,
            precision_pm,
            precision_note,
            month: 1.0,
            doy: 15.0,
            is_weekend: false,
            oat_midnight_f: 15.0,
            oat_amplitude_f: 10.0,
            oat_manual: oat,
            use_manual_oat: true,
            midnight_zone_f: [62.0; 6],
            strategy_idx: 1, // stagger_preheat default DSM
            hp_on,
            use_strategy_occ: true,
            occ_override: occ,
            energy_rate_per_kwh: tariff.energy_on_peak_per_kwh,
            demand_rate_per_kw: tariff.demand_per_kw,
            similar_days_per_year: 90.0,
            rate_label: tariff.label.clone(),
            rate_honesty: tariff.honesty.clone(),
            use_tod_tariff: true,
            tariff,
            bill_book: None,
            bill_error: None,
            bill_warnings: Vec::new(),
            rate_preset_idx: 0,
            monthly_book: None,
            monthly_error: None,
            on_peak_energy_share: 0.55,
            ratchet_tol_kw: 5.0,
            pred_kw_compare: [0.0; 24],
            pred_kw_dsm: [0.0; 24],
            compare_label: "HVAC 24/7".into(),
            dsm_label: "stagger_preheat".into(),
            cost_compare: None,
            cost_dsm: None,
            annual: None,
            mvm: load_mvm_bundle(),
            status: "Tariff defaults = Creekside CP-2 (editable). Run Compare 24/7 vs DSM."
                .into(),
        };

        match try_autoload_bills() {
            Ok(Some(book)) => app.apply_bill_book(book),
            Ok(None) => {}
            Err(e) => {
                app.bill_error = Some(format!(
                    "Auto-load utility CSV failed (app still runs):\n{}",
                    e.message
                ));
            }
        }

        if let Some(path) = annual_sample_candidates()
            .into_iter()
            .find(|p| p.is_file())
        {
            match MonthlyBook::load_csv(&path) {
                Ok(book) => {
                    app.status = format!(
                        "Loaded {} monthly peaks from {}",
                        book.rows.len(),
                        book.path
                    );
                    app.monthly_book = Some(book);
                }
                Err(e) => app.monthly_error = Some(format!("{e:#}")),
            }
        }

        app
    }

    fn apply_derived(&mut self, rates: DerivedRates) {
        self.energy_rate_per_kwh = rates.energy_rate_per_kwh;
        self.demand_rate_per_kw = rates.demand_rate_per_kw;
        self.rate_label = rates.label.clone();
        self.rate_honesty = rates.honesty.clone();
        for w in rates.warnings {
            if !self.bill_warnings.contains(&w) {
                self.bill_warnings.push(w);
            }
        }
    }

    fn apply_bill_book(&mut self, book: BillBook) {
        self.bill_warnings = book.warnings.clone();
        self.bill_error = None;
        match book.default_rates() {
            Ok(rates) => {
                self.rate_preset_idx = if book.heating_season.is_some() {
                    0
                } else if book.all_months_ols.is_some() {
                    1
                } else {
                    2
                };
                self.apply_derived(rates);
                self.bill_book = Some(book);
            }
            Err(e) => {
                self.bill_error = Some(e.message);
                self.bill_book = Some(book);
            }
        }
    }

    fn apply_rate_preset(&mut self) {
        let Some(book) = self.bill_book.clone() else {
            return;
        };
        let result = match self.rate_preset_idx {
            0 => book
                .heating_season
                .clone()
                .ok_or_else(|| bills::BillLoadError {
                    message: "Heating-season OLS unavailable.".into(),
                }),
            1 => book
                .all_months_ols
                .clone()
                .ok_or_else(|| bills::BillLoadError {
                    message: "All-months OLS unavailable.".into(),
                }),
            i => {
                let mi = i.saturating_sub(2);
                book.rows
                    .get(mi)
                    .map(|r| r.month_key.clone())
                    .ok_or_else(|| bills::BillLoadError {
                        message: "Invalid month preset index.".into(),
                    })
                    .and_then(|mk| book.rates_for_month(&mk))
            }
        };
        match result {
            Ok(rates) => {
                self.bill_error = None;
                self.apply_derived(rates);
            }
            Err(e) => self.bill_error = Some(e.message),
        }
    }

    fn pick_and_load_bills(&mut self) {
        let path = rfd::FileDialog::new()
            .add_filter("CSV", &["csv"])
            .set_title("Load utility bill CSV")
            .pick_file();
        let Some(path) = path else {
            return;
        };
        match bills::load_bill_csv(&path) {
            Ok(book) => self.apply_bill_book(book),
            Err(e) => {
                self.bill_error = Some(e.message);
                self.status = "Utility CSV rejected.".into();
            }
        }
    }

    fn pick_and_load_monthly(&mut self) {
        let path = rfd::FileDialog::new()
            .add_filter("CSV", &["csv"])
            .set_title("Load monthly peaks CSV (demand / billed demand)")
            .pick_file();
        let Some(path) = path else {
            return;
        };
        match MonthlyBook::load_csv(&path) {
            Ok(book) => {
                self.monthly_error = None;
                self.status = format!("Monthly peaks: {} rows", book.rows.len());
                self.monthly_book = Some(book);
                self.refresh_annual();
            }
            Err(e) => self.monthly_error = Some(format!("{e:#}")),
        }
    }

    fn reset_tariff_defaults(&mut self) {
        self.tariff = creekside_cp2_defaults();
        self.use_tod_tariff = true;
        self.rate_label = self.tariff.label.clone();
        self.rate_honesty = self.tariff.honesty.clone();
        self.energy_rate_per_kwh = self.tariff.energy_on_peak_per_kwh;
        self.demand_rate_per_kw = self.tariff.demand_per_kw;
        self.status = "Restored Creekside CP-2 tariff defaults.".into();
        self.reprice_days();
    }

    fn oat_at(&self, hour: usize) -> f32 {
        if self.use_manual_oat {
            self.oat_manual[hour]
        } else {
            let phase = ((hour as f32 - 6.0) / 24.0) * 2.0 * std::f32::consts::PI;
            self.oat_midnight_f + self.oat_amplitude_f * (0.5 - 0.5 * phase.cos())
        }
    }

    fn apply_strategy_defaults(&mut self) {
        let sid = STRATEGY_IDS[self.strategy_idx];
        for h in 0..24 {
            let o = default_occ_frac(h, sid, self.is_weekend);
            self.occ_override[h] = o;
            for z in 0..6 {
                self.hp_on[h][z] = o[z] > 0.05;
            }
        }
    }

    fn apply_flat_24_7_grid(&mut self) {
        self.strategy_idx = STRATEGY_IDS
            .iter()
            .position(|s| *s == "flat_24_7")
            .unwrap_or(2);
        for h in 0..24 {
            self.occ_override[h] = [1.0; 6];
            self.hp_on[h] = [true; 6];
        }
        self.use_strategy_occ = true;
    }

    fn day_cost(&self, kw: &[f32; 24]) -> TodDayCost {
        let month = self.month.round().clamp(1.0, 12.0) as u8;
        if self.use_tod_tariff {
            cost_day_tod(kw, &self.tariff, self.is_weekend, month, false)
        } else {
            let energy_kwh: f32 = kw.iter().sum();
            let peak_kw = kw.iter().copied().fold(0.0_f32, f32::max);
            let energy_cost = energy_kwh * self.energy_rate_per_kwh;
            let demand_cost = peak_kw * self.demand_rate_per_kw;
            TodDayCost {
                energy_kwh,
                on_peak_kwh: energy_kwh,
                off_peak_kwh: 0.0,
                peak_kw,
                energy_on_peak_cost: energy_cost,
                energy_off_peak_cost: 0.0,
                pca_cost: 0.0,
                demand_cost,
                distribution_demand_cost: 0.0,
                customer_charge_day_share: 0.0,
                total_cost: energy_cost + demand_cost,
            }
        }
    }

    fn reprice_days(&mut self) {
        if self.pred_kw_compare.iter().any(|v| *v > 0.0) {
            self.cost_compare = Some(self.day_cost(&self.pred_kw_compare));
        }
        if self.pred_kw_dsm.iter().any(|v| *v > 0.0) {
            self.cost_dsm = Some(self.day_cost(&self.pred_kw_dsm));
        }
        self.refresh_annual();
    }

    fn refresh_annual(&mut self) {
        let (Some(book), Some(cc), Some(cd)) =
            (&self.monthly_book, &self.cost_compare, &self.cost_dsm)
        else {
            self.annual = None;
            return;
        };
        let delta_peak = (cc.peak_kw - cd.peak_kw).max(0.0);
        let delta_kwh = cd.energy_kwh - cc.energy_kwh;
        self.annual = Some(rollup_annual_savings(
            book,
            &self.tariff,
            delta_peak,
            delta_kwh,
            self.similar_days_per_year,
            self.on_peak_energy_share,
            self.ratchet_tol_kw,
        ));
    }

    /// Run one 24h ONNX walk for a strategy id with optional forced 24/7 grid.
    fn predict_profile(&mut self, strategy_id: &str, force_247: bool) -> Option<[f32; 24]> {
        if self.model.is_none() {
            self.status = self
                .load_error
                .clone()
                .unwrap_or_else(|| "No model loaded".into());
            return None;
        }

        let oat_profile: [f32; 24] = std::array::from_fn(|h| self.oat_at(h));
        let knobs = StrategyKnobs::for_id(strategy_id);
        let weekend = self.is_weekend;
        let month = self.month;
        let doy = self.doy;
        let use_strategy_occ = self.use_strategy_occ;
        let hp_on = self.hp_on;
        let occ_override = self.occ_override;

        let mut lag1 = 35.0_f32;
        let mut lag2 = 35.0_f32;
        let mut cum_hdd_night = 0.0_f32;
        let mut pred = [0.0_f32; 24];
        let model = self.model.as_mut().unwrap();

        for h in 0..24 {
            let oat = oat_profile[h];
            let oat_lag1 = if h == 0 { oat } else { oat_profile[h - 1] };
            let hdd = (65.0 - oat).max(0.0);
            if h < 5 || h >= 20 {
                cum_hdd_night += hdd;
            }

            let (occ, hp) = if force_247 {
                ([1.0_f32; 6], [1.0_f32; 6])
            } else if use_strategy_occ {
                let o = default_occ_frac(h, strategy_id, weekend);
                let mut hp = [0.0_f32; 6];
                for z in 0..6 {
                    hp[z] = if o[z] > 0.05 { 1.0 } else { 0.0 };
                }
                (o, hp)
            } else {
                let mut hp = [0.0_f32; 6];
                for z in 0..6 {
                    hp[z] = if hp_on[h][z] { 1.0 } else { 0.0 };
                }
                (occ_override[h], hp)
            };

            let inputs = HourInputs {
                hour_ending: h as f32,
                month,
                doy,
                is_weekend: if weekend { 1.0 } else { 0.0 },
                oat_f: oat,
                oat_lag1,
                rh_pct: 55.0,
                ghi: if (8..17).contains(&h) { 200.0 } else { 0.0 },
                occ_frac: occ,
                hp_on: hp,
                knobs: knobs.clone(),
                strategy_id: strategy_id.to_string(),
                facility_kw_lag1: lag1,
                facility_kw_lag2: lag2,
                hdd65_cum_night: cum_hdd_night,
            };

            let feat = build_features(&inputs);
            match model.predict_kw(&feat) {
                Ok(kw) => {
                    let kw = kw.max(5.0);
                    pred[h] = kw;
                    lag2 = lag1;
                    lag1 = kw;
                }
                Err(e) => {
                    self.status = format!("ONNX infer failed at hour {h}: {e:#}");
                    return None;
                }
            }
        }
        Some(pred)
    }

    fn run_compare_247_vs_dsm(&mut self) {
        let dsm_sid = STRATEGY_IDS[self.strategy_idx].to_string();
        let Some(kw247) = self.predict_profile("flat_24_7", true) else {
            return;
        };
        let Some(kw_dsm) = self.predict_profile(&dsm_sid, false) else {
            return;
        };
        self.pred_kw_compare = kw247;
        self.pred_kw_dsm = kw_dsm;
        self.compare_label = "HVAC 24/7".into();
        self.dsm_label = dsm_sid;
        self.cost_compare = Some(self.day_cost(&self.pred_kw_compare));
        self.cost_dsm = Some(self.day_cost(&self.pred_kw_dsm));
        self.refresh_annual();
        let pc = self.cost_compare.as_ref().unwrap().peak_kw;
        let pd = self.cost_dsm.as_ref().unwrap().peak_kw;
        let ec = self.cost_compare.as_ref().unwrap().energy_kwh;
        let ed = self.cost_dsm.as_ref().unwrap().energy_kwh;
        self.status = format!(
            "Compare OK — 24/7 peak {:.1} vs DSM {:.1} (Δpeak {:.1} kW) · ΣkWh {:.0}→{:.0}",
            pc,
            pd,
            (pc - pd).max(0.0),
            ec,
            ed
        );
    }

    fn run_dsm_only(&mut self) {
        let dsm_sid = STRATEGY_IDS[self.strategy_idx].to_string();
        let Some(kw) = self.predict_profile(&dsm_sid, false) else {
            return;
        };
        self.pred_kw_dsm = kw;
        self.dsm_label = dsm_sid;
        self.cost_dsm = Some(self.day_cost(&self.pred_kw_dsm));
        if self.pred_kw_compare.iter().all(|v| *v == 0.0) {
            self.pred_kw_compare = self.pred_kw_dsm;
            self.compare_label = self.dsm_label.clone();
            self.cost_compare = self.cost_dsm.clone();
        }
        self.refresh_annual();
        let peak = self.pred_kw_dsm.iter().copied().fold(0.0_f32, f32::max);
        self.status = format!(
            "DSM walk OK — peak={peak:.1} ±{:.1} kW · {}",
            self.precision_pm, self.model_name
        );
    }
}

fn annual_sample_candidates() -> Vec<std::path::PathBuf> {
    let mut out = Vec::new();
    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            out.push(dir.join("creeksides_e1075_bills.csv"));
        }
    }
    out.push(
        std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .join("data")
            .join("sample")
            .join("creeksides_e1075_bills.csv"),
    );
    out
}

fn cost_bars(c: &TodDayCost, offset: f64) -> Vec<Bar> {
    vec![
        Bar::new(0.0 + offset, c.energy_on_peak_cost as f64).name("on-peak $"),
        Bar::new(1.0 + offset, c.energy_off_peak_cost as f64).name("off-peak $"),
        Bar::new(2.0 + offset, c.pca_cost as f64).name("PCA $"),
        Bar::new(3.0 + offset, c.demand_cost as f64).name("demand $"),
        Bar::new(4.0 + offset, c.distribution_demand_cost as f64).name("dist $"),
    ]
}

impl eframe::App for DsmApp {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        egui::TopBottomPanel::top("banner").show(ctx, |ui| {
            ui.add_space(4.0);
            ui.horizontal(|ui| {
                ui.heading(
                    egui::RichText::new("Lakeside Heating DSM")
                        .color(egui::Color32::from_rgb(232, 168, 96)),
                );
                ui.separator();
                ui.label(
                    egui::RichText::new(&self.model_banner)
                        .strong()
                        .color(egui::Color32::from_rgb(210, 220, 230)),
                );
                ui.separator();
                ui.label(format!("Tariff: {}", self.tariff.label));
            });
            ui.label(
                egui::RichText::new(format!(
                    "ONNX: {}  ·  training_source={}",
                    self.onnx_path_display, self.training_source
                ))
                .small()
                .weak(),
            );
            if !self.honesty.is_empty() {
                ui.colored_label(egui::Color32::from_rgb(210, 150, 70), &self.honesty);
            }
            if let Some(err) = &self.load_error {
                ui.colored_label(egui::Color32::from_rgb(230, 80, 80), err);
            }
            ui.add_space(4.0);
        });

        egui::SidePanel::left("controls")
            .default_width(380.0)
            .show(ctx, |ui| {
                egui::ScrollArea::vertical().show(ui, |ui| {
                    ui.heading("Portable tariff");
                    ui.label("Any utility demand/TOD rates — Creekside CP-2 prefilled.");
                    ui.checkbox(&mut self.use_tod_tariff, "Use TOD + dual demand tariff");
                    if ui.button("↺ Reset to Creekside CP-2 defaults").clicked() {
                        self.reset_tariff_defaults();
                    }
                    ui.add(
                        egui::TextEdit::singleline(&mut self.tariff.label)
                            .desired_width(340.0)
                            .hint_text("tariff label"),
                    );
                    egui::Grid::new("tariff_grid")
                        .num_columns(2)
                        .spacing([8.0, 4.0])
                        .show(ui, |ui| {
                            ui.label("On-peak $/kWh");
                            if ui
                                .add(
                                    egui::DragValue::new(&mut self.tariff.energy_on_peak_per_kwh)
                                        .speed(0.001)
                                        .range(0.0..=2.0),
                                )
                                .changed()
                            {
                                self.reprice_days();
                            }
                            ui.end_row();
                            ui.label("Off-peak $/kWh");
                            if ui
                                .add(
                                    egui::DragValue::new(&mut self.tariff.energy_off_peak_per_kwh)
                                        .speed(0.001)
                                        .range(0.0..=2.0),
                                )
                                .changed()
                            {
                                self.reprice_days();
                            }
                            ui.end_row();
                            ui.label("PCA $/kWh");
                            if ui
                                .add(
                                    egui::DragValue::new(&mut self.tariff.pca_per_kwh)
                                        .speed(0.0001)
                                        .range(0.0..=0.5),
                                )
                                .changed()
                            {
                                self.reprice_days();
                            }
                            ui.end_row();
                            ui.label("Demand $/kW");
                            if ui
                                .add(
                                    egui::DragValue::new(&mut self.tariff.demand_per_kw)
                                        .speed(0.25)
                                        .range(0.0..=100.0),
                                )
                                .changed()
                            {
                                self.reprice_days();
                            }
                            ui.end_row();
                            ui.label("Dist demand $/kW");
                            if ui
                                .add(
                                    egui::DragValue::new(
                                        &mut self.tariff.distribution_demand_per_kw,
                                    )
                                    .speed(0.05)
                                    .range(0.0..=50.0),
                                )
                                .changed()
                            {
                                self.reprice_days();
                            }
                            ui.end_row();
                            ui.label("Customer $/mo");
                            ui.add(
                                egui::DragValue::new(&mut self.tariff.customer_charge)
                                    .speed(1.0)
                                    .range(0.0..=5000.0),
                            );
                            ui.end_row();
                            ui.label("On-peak HE start");
                            ui.add(
                                egui::DragValue::new(&mut self.tariff.on_peak_he_start)
                                    .range(0..=23),
                            );
                            ui.end_row();
                            ui.label("On-peak HE end");
                            ui.add(
                                egui::DragValue::new(&mut self.tariff.on_peak_he_end).range(1..=24),
                            );
                            ui.end_row();
                        });
                    ui.checkbox(&mut self.tariff.weekends_off_peak, "Weekends off-peak");
                    ui.checkbox(&mut self.tariff.use_step_up, "Aug+ rate step-up");
                    if self.tariff.use_step_up {
                        ui.horizontal(|ui| {
                            ui.label("from month");
                            ui.add(
                                egui::DragValue::new(&mut self.tariff.step_up_from_month)
                                    .range(1..=12),
                            );
                            ui.label("dem");
                            ui.add(
                                egui::DragValue::new(&mut self.tariff.demand_per_kw_step)
                                    .speed(0.05),
                            );
                            ui.label("dist");
                            ui.add(
                                egui::DragValue::new(
                                    &mut self.tariff.distribution_demand_per_kw_step,
                                )
                                .speed(0.05),
                            );
                        });
                    }
                    ui.colored_label(
                        egui::Color32::from_rgb(120, 160, 190),
                        &self.tariff.honesty,
                    );

                    if !self.use_tod_tariff {
                        ui.separator();
                        ui.heading("Flat rates (legacy)");
                        ui.add(
                            egui::DragValue::new(&mut self.energy_rate_per_kwh)
                                .speed(0.001)
                                .prefix("$")
                                .suffix(" /kWh"),
                        );
                        ui.add(
                            egui::DragValue::new(&mut self.demand_rate_per_kw)
                                .speed(0.25)
                                .prefix("$")
                                .suffix(" /kW"),
                        );
                    }

                    ui.separator();
                    ui.heading("Utility / monthly peaks");
                    if ui
                        .add_sized(
                            [340.0, 26.0],
                            egui::Button::new("📂 Load bill CSV (OLS rates)…"),
                        )
                        .clicked()
                    {
                        self.pick_and_load_bills();
                    }
                    if ui
                        .add_sized(
                            [340.0, 26.0],
                            egui::Button::new("📂 Load monthly peaks CSV…"),
                        )
                        .clicked()
                    {
                        self.pick_and_load_monthly();
                    }
                    if let Some(book) = &self.monthly_book {
                        ui.label(format!(
                            "Peaks: {} mo · max demand {:.0} · max billed {:.0}",
                            book.rows.len(),
                            book.max_demand_kw(),
                            book.max_billed_demand_kw()
                        ));
                    }
                    if let Some(err) = &self.monthly_error {
                        ui.colored_label(egui::Color32::from_rgb(220, 90, 90), err);
                    }
                    if let Some(book) = &self.bill_book {
                        ui.label(format!("OLS bills: {} mo", book.rows.len()));
                        let prev = self.rate_preset_idx;
                        let mut labels: Vec<String> = vec![
                            "Heating season OLS".into(),
                            "All months OLS".into(),
                        ];
                        for r in &book.rows {
                            labels.push(format!("Month {}", r.month_key));
                        }
                        let selected = labels
                            .get(self.rate_preset_idx)
                            .cloned()
                            .unwrap_or_else(|| "(none)".into());
                        egui::ComboBox::from_label("OLS preset")
                            .selected_text(selected)
                            .width(260.0)
                            .show_ui(ui, |ui| {
                                for (i, lab) in labels.iter().enumerate() {
                                    ui.selectable_value(&mut self.rate_preset_idx, i, lab);
                                }
                            });
                        if prev != self.rate_preset_idx {
                            self.apply_rate_preset();
                        }
                    }
                    for w in &self.bill_warnings {
                        ui.colored_label(
                            egui::Color32::from_rgb(160, 120, 40),
                            format!("⚠ {w}"),
                        );
                    }
                    if let Some(err) = &self.bill_error {
                        ui.colored_label(egui::Color32::from_rgb(220, 90, 90), err);
                    }

                    ui.separator();
                    ui.heading("Day / weather");
                    ui.add(egui::Slider::new(&mut self.month, 1.0..=12.0).text("month"));
                    ui.add(egui::Slider::new(&mut self.doy, 1.0..=366.0).text("day of year"));
                    ui.checkbox(&mut self.is_weekend, "Weekend");
                    ui.checkbox(&mut self.use_manual_oat, "Edit 24h OAT (°F)");
                    if !self.use_manual_oat {
                        ui.add(
                            egui::Slider::new(&mut self.oat_midnight_f, -20.0..=50.0)
                                .text("OAT base °F"),
                        );
                        ui.add(
                            egui::Slider::new(&mut self.oat_amplitude_f, 0.0..=25.0)
                                .text("diurnal amp °F"),
                        );
                    } else {
                        egui::ScrollArea::vertical()
                            .max_height(90.0)
                            .id_salt("oat_scroll")
                            .show(ui, |ui| {
                                for h in 0..24 {
                                    ui.add(
                                        egui::Slider::new(&mut self.oat_manual[h], -30.0..=70.0)
                                            .text(format!("OAT HE{h:02}")),
                                    );
                                }
                            });
                    }

                    ui.separator();
                    ui.heading("DSM strategy");
                    let prev = self.strategy_idx;
                    egui::ComboBox::from_label("strategy")
                        .selected_text(STRATEGY_IDS[self.strategy_idx])
                        .show_ui(ui, |ui| {
                            for (i, s) in STRATEGY_IDS.iter().enumerate() {
                                ui.selectable_value(&mut self.strategy_idx, i, *s);
                            }
                        });
                    if prev != self.strategy_idx {
                        self.apply_strategy_defaults();
                    }
                    ui.checkbox(&mut self.use_strategy_occ, "Use strategy occ fractions");
                    if ui.button("Reset HP grid from strategy").clicked() {
                        self.apply_strategy_defaults();
                    }
                    if ui.button("Fill grid = HVAC all day (24/7)").clicked() {
                        self.apply_flat_24_7_grid();
                    }

                    ui.separator();
                    ui.heading("Annual rollup knobs");
                    ui.add(
                        egui::DragValue::new(&mut self.similar_days_per_year)
                            .speed(1.0)
                            .range(1.0..=200.0)
                            .suffix(" similar cold days"),
                    );
                    ui.add(
                        egui::DragValue::new(&mut self.on_peak_energy_share)
                            .speed(0.01)
                            .range(0.0..=1.0)
                            .suffix(" on-peak energy share"),
                    );
                    ui.add(
                        egui::DragValue::new(&mut self.ratchet_tol_kw)
                            .speed(0.5)
                            .range(0.0..=50.0)
                            .suffix(" kW ratchet tol"),
                    );
                    if ui.button("Refresh annual rollup").clicked() {
                        self.refresh_annual();
                    }

                    ui.separator();
                    if ui
                        .add_sized(
                            [340.0, 42.0],
                            egui::Button::new(
                                egui::RichText::new("▶  Compare HVAC 24/7 vs DSM")
                                    .size(15.0)
                                    .strong(),
                            )
                            .fill(egui::Color32::from_rgb(196, 110, 48)),
                        )
                        .clicked()
                    {
                        self.run_compare_247_vs_dsm();
                    }
                    if ui
                        .add_sized([340.0, 28.0], egui::Button::new("Run DSM walk only"))
                        .clicked()
                    {
                        self.run_dsm_only();
                    }
                    ui.label(
                        egui::RichText::new(&self.status)
                            .color(egui::Color32::from_rgb(180, 200, 190)),
                    );

                    ui.collapsing("Midnight zone temps (°F)", |ui| {
                        ui.weak("Placeholder — kW model only.");
                        for z in 0..6 {
                            ui.add(
                                egui::Slider::new(&mut self.midnight_zone_f[z], 50.0..=75.0)
                                    .text(ZONE_LABELS[z]),
                            );
                        }
                    });
                });
            });

        egui::CentralPanel::default().show(ctx, |ui| {
            egui::ScrollArea::vertical().show(ui, |ui| {
                egui::CollapsingHeader::new("Measured vs modeled validation")
                    .default_open(true)
                    .show(ui, |ui| {
                        show_mvm_panel(ui, &self.mvm);
                    });
                ui.add_space(8.0);
                egui::Frame::group(ui.style())
                    .fill(egui::Color32::from_rgb(34, 42, 50))
                    .inner_margin(12.0)
                    .show(ui, |ui| {
                        ui.horizontal(|ui| {
                            ui.heading(
                                egui::RichText::new(&self.model_name)
                                    .color(egui::Color32::from_rgb(232, 168, 96)),
                            );
                            ui.separator();
                            ui.label(
                                egui::RichText::new(format!(
                                    "screening peak MAE {:.1} kW (not an uncertainty interval)",
                                    self.precision_pm
                                ))
                                .strong()
                                .color(egui::Color32::from_rgb(140, 200, 160)),
                            );
                        });
                        for line in &self.metrics_lines {
                            ui.label(egui::RichText::new(line).monospace());
                        }
                        if !self.precision_note.is_empty() {
                            ui.label(
                                egui::RichText::new(&self.precision_note)
                                    .small()
                                    .italics()
                                    .weak(),
                            );
                        }
                        ui.collapsing("Tuned hyperparameters", |ui| {
                            egui::Grid::new("param_grid")
                                .num_columns(2)
                                .striped(true)
                                .show(ui, |ui| {
                                    for (k, v) in &self.param_rows {
                                        ui.label(
                                            egui::RichText::new(k)
                                                .monospace()
                                                .color(egui::Color32::from_rgb(160, 180, 200)),
                                        );
                                        ui.label(egui::RichText::new(v).monospace().strong());
                                        ui.end_row();
                                    }
                                });
                        });
                    });

                ui.add_space(8.0);
                ui.heading("kW overlay — 24/7 vs DSM");
                let pm = self.precision_pm as f64;
                let cmp: PlotPoints = (0..24)
                    .map(|h| [h as f64, self.pred_kw_compare[h] as f64])
                    .collect();
                let dsm: PlotPoints = (0..24)
                    .map(|h| [h as f64, self.pred_kw_dsm[h] as f64])
                    .collect();
                let dsm_lo: PlotPoints = (0..24)
                    .map(|h| [h as f64, (self.pred_kw_dsm[h] as f64 - pm).max(0.0)])
                    .collect();
                let dsm_hi: PlotPoints = (0..24)
                    .map(|h| [h as f64, self.pred_kw_dsm[h] as f64 + pm])
                    .collect();
                Plot::new("kw_overlay")
                    .height(260.0)
                    .legend(egui_plot::Legend::default())
                    .show(ui, |plot_ui| {
                        plot_ui.line(
                            Line::new(dsm_hi)
                                .name(format!("DSM +{pm:.0}"))
                                .color(egui::Color32::from_rgb(70, 100, 120))
                                .width(1.0),
                        );
                        plot_ui.line(
                            Line::new(dsm_lo)
                                .name(format!("DSM −{pm:.0}"))
                                .color(egui::Color32::from_rgb(70, 100, 120))
                                .width(1.0),
                        );
                        plot_ui.line(
                            Line::new(cmp)
                                .name(&self.compare_label)
                                .color(egui::Color32::from_rgb(180, 90, 90))
                                .width(2.2),
                        );
                        plot_ui.line(
                            Line::new(dsm)
                                .name(&self.dsm_label)
                                .color(egui::Color32::from_rgb(232, 140, 64))
                                .width(2.6),
                        );
                    });

                ui.add_space(6.0);
                ui.heading("Hourly kWh (same as kW · 1h)");
                let bars_cmp: Vec<Bar> = (0..24)
                    .map(|h| {
                        Bar::new(h as f64 - 0.15, self.pred_kw_compare[h] as f64)
                            .width(0.28)
                            .name(&self.compare_label)
                    })
                    .collect();
                let bars_dsm: Vec<Bar> = (0..24)
                    .map(|h| {
                        Bar::new(h as f64 + 0.15, self.pred_kw_dsm[h] as f64)
                            .width(0.28)
                            .name(&self.dsm_label)
                    })
                    .collect();
                Plot::new("kwh_bars")
                    .height(180.0)
                    .legend(egui_plot::Legend::default())
                    .show(ui, |plot_ui| {
                        plot_ui.bar_chart(
                            BarChart::new(bars_cmp)
                                .color(egui::Color32::from_rgb(160, 80, 80)),
                        );
                        plot_ui.bar_chart(
                            BarChart::new(bars_dsm)
                                .color(egui::Color32::from_rgb(220, 130, 50)),
                        );
                    });

                ui.separator();
                ui.heading("Day cost breakdown");
                match (&self.cost_compare, &self.cost_dsm) {
                    (Some(cc), Some(cd)) => {
                        egui::Grid::new("day_cost_cmp")
                            .num_columns(3)
                            .striped(true)
                            .show(ui, |ui| {
                                ui.label("");
                                ui.strong(&self.compare_label);
                                ui.strong(&self.dsm_label);
                                ui.end_row();
                                ui.label("Peak kW");
                                ui.label(format!("{:.1}", cc.peak_kw));
                                ui.label(format!("{:.1}", cd.peak_kw));
                                ui.end_row();
                                ui.label("Σ kWh");
                                ui.label(format!("{:.0}", cc.energy_kwh));
                                ui.label(format!("{:.0}", cd.energy_kwh));
                                ui.end_row();
                                ui.label("On-peak kWh");
                                ui.label(format!("{:.0}", cc.on_peak_kwh));
                                ui.label(format!("{:.0}", cd.on_peak_kwh));
                                ui.end_row();
                                ui.label("Off-peak kWh");
                                ui.label(format!("{:.0}", cc.off_peak_kwh));
                                ui.label(format!("{:.0}", cd.off_peak_kwh));
                                ui.end_row();
                                ui.label("Energy $");
                                ui.label(format!(
                                    "{:.2}",
                                    cc.energy_on_peak_cost + cc.energy_off_peak_cost + cc.pca_cost
                                ));
                                ui.label(format!(
                                    "{:.2}",
                                    cd.energy_on_peak_cost + cd.energy_off_peak_cost + cd.pca_cost
                                ));
                                ui.end_row();
                                ui.label("Demand $");
                                ui.label(format!("{:.2}", cc.demand_cost));
                                ui.label(format!("{:.2}", cd.demand_cost));
                                ui.end_row();
                                ui.label("Dist demand $");
                                ui.label(format!("{:.2}", cc.distribution_demand_cost));
                                ui.label(format!("{:.2}", cd.distribution_demand_cost));
                                ui.end_row();
                                ui.label("Day total $");
                                ui.strong(format!("{:.2}", cc.total_cost));
                                ui.strong(format!("{:.2}", cd.total_cost));
                                ui.end_row();
                                ui.label("Δpeak / ΔkWh");
                                ui.label("—");
                                ui.strong(format!(
                                    "{:.1} kW / {:+.0} kWh",
                                    (cc.peak_kw - cd.peak_kw).max(0.0),
                                    cd.energy_kwh - cc.energy_kwh
                                ));
                                ui.end_row();
                            });

                        Plot::new("cost_bars")
                            .height(160.0)
                            .show(ui, |plot_ui| {
                                plot_ui.bar_chart(
                                    BarChart::new(cost_bars(cc, -0.18))
                                        .width(0.32)
                                        .color(egui::Color32::from_rgb(160, 80, 80))
                                        .name(&self.compare_label),
                                );
                                plot_ui.bar_chart(
                                    BarChart::new(cost_bars(cd, 0.18))
                                        .width(0.32)
                                        .color(egui::Color32::from_rgb(220, 130, 50))
                                        .name(&self.dsm_label),
                                );
                            });
                    }
                    _ => {
                        ui.label("Run Compare HVAC 24/7 vs DSM to populate charts.");
                    }
                }

                ui.separator();
                ui.heading("Annual demand savings (heuristic)");
                if let Some(a) = &self.annual {
                    egui::Frame::group(ui.style())
                        .fill(egui::Color32::from_rgb(34, 42, 50))
                        .inner_margin(10.0)
                        .show(ui, |ui| {
                            egui::Grid::new("annual_grid")
                                .num_columns(2)
                                .striped(true)
                                .show(ui, |ui| {
                                    ui.label("Months used");
                                    ui.label(format!("{}", a.months_used));
                                    ui.end_row();
                                    ui.label("Baseline demand $");
                                    ui.label(format!("${:.0}", a.baseline_demand_cost));
                                    ui.end_row();
                                    ui.label("DSM demand $");
                                    ui.label(format!("${:.0}", a.dsm_demand_cost));
                                    ui.end_row();
                                    ui.label("Baseline dist $");
                                    ui.label(format!("${:.0}", a.baseline_dist_cost));
                                    ui.end_row();
                                    ui.label("DSM dist $");
                                    ui.label(format!("${:.0}", a.dsm_dist_cost));
                                    ui.end_row();
                                    ui.label("Δpeak applied");
                                    ui.label(format!("{:.1} kW", a.delta_peak_kw));
                                    ui.end_row();
                                    ui.label("Demand $ savings");
                                    ui.label(format!("${:.0}", a.demand_savings));
                                    ui.end_row();
                                    ui.label("Dist demand $ savings");
                                    ui.label(format!("${:.0}", a.dist_savings));
                                    ui.end_row();
                                    ui.label("Energy penalty (cold days)");
                                    ui.label(format!(
                                        "${:.0}  (Δ{:+.0} kWh/day × {:.0})",
                                        a.energy_penalty, a.delta_kwh_day, a.similar_cold_days
                                    ));
                                    ui.end_row();
                                    ui.label("Net annual savings");
                                    ui.strong(
                                        egui::RichText::new(format!(
                                            "${:.0}",
                                            a.net_annual_savings
                                        ))
                                        .size(18.0)
                                        .color(egui::Color32::from_rgb(140, 200, 160)),
                                    );
                                    ui.end_row();
                                    ui.label("Ratchet months shaved");
                                    ui.label(format!("{}", a.ratchet_months_shaved));
                                    ui.end_row();
                                });
                            ui.colored_label(
                                egui::Color32::from_rgb(160, 170, 180),
                                &a.note,
                            );
                        });
                } else {
                    ui.label(
                        "Load monthly peaks CSV and run Compare to estimate annual demand savings.",
                    );
                }

                if let Some(book) = &self.monthly_book {
                    ui.collapsing("Monthly peaks table", |ui| {
                        egui::Grid::new("mo_tbl").striped(true).show(ui, |ui| {
                            ui.label("Month");
                            ui.label("kWh");
                            ui.label("Demand");
                            ui.label("Billed");
                            ui.label("Cost $");
                            ui.end_row();
                            for r in &book.rows {
                                ui.label(&r.month);
                                ui.label(
                                    r.kwh
                                        .map(|v| format!("{v:.0}"))
                                        .unwrap_or_else(|| "—".into()),
                                );
                                ui.label(
                                    r.demand_kw
                                        .map(|v| format!("{v:.1}"))
                                        .unwrap_or_else(|| "—".into()),
                                );
                                ui.label(
                                    r.billed_demand_kw
                                        .map(|v| format!("{v:.1}"))
                                        .unwrap_or_else(|| "—".into()),
                                );
                                ui.label(
                                    r.cost_usd
                                        .map(|v| format!("{v:.0}"))
                                        .unwrap_or_else(|| "—".into()),
                                );
                                ui.end_row();
                            }
                        });
                    });
                }
            });
        });
    }
}
