//! Lakeside heating DSM desktop walk — egui + ONNX.
//!
//! Portable TOD + dual-demand tariff (Creekside CP-2 defaults prefilled).
//! Dual walks: HVAC 24/7 vs DSM strategy → Δpeak / ΔkWh + annual rollup.

mod annual;
mod bills;
mod control_contract;
mod features;
mod features_15min;
mod hybrid;
mod hybrid_onnx;
#[allow(dead_code)]
mod model; // quarantined hourly heating_dsm_hourly_v1 path — unused by live UI
mod mvm;
mod tariff;

use annual::{rollup_annual_savings, AnnualRollup, MonthlyBook};
use bills::{try_autoload_bills, BillBook, DerivedRates};
use eframe::egui;
use egui_plot::{Bar, BarChart, Line, Plot, PlotPoints};
use features::{default_occ_frac, STRATEGY_IDS, ZONE_LABELS};
use hybrid::{load_hybrid_walk, show_hybrid_panel, HybridWalk};
use hybrid_onnx::{expand_oat_24_to_96, HybridEngine};
use features_15min::STEPS_96;
use mvm::{load_mvm_bundle, show_mvm_panel, MvmBundle};
use tariff::{
    cost_day_tod, cost_day_tod_96, creekside_cp2_defaults, hourly_mean_from_quarters, DemandTariff,
    TodDayCost,
};

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
    hybrid_engine: Option<HybridEngine>,
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
    midnight_facility_kw: f32,
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

    // Dual walk results (hourly downsample of live hybrid for tariff charts)
    pred_kw_compare: [f32; 24],
    pred_kw_dsm: [f32; 24],
    compare_label: String,
    dsm_label: String,
    cost_compare: Option<TodDayCost>,
    cost_dsm: Option<TodDayCost>,
    annual: Option<AnnualRollup>,
    mvm: MvmBundle,
    hybrid_walk: Option<HybridWalk>,
    hybrid_path: Option<std::path::PathBuf>,
    hybrid_error: Option<String>,
    ship_walk: Option<HybridWalk>,
    ship_path: Option<std::path::PathBuf>,
    status: String,
}

impl DsmApp {
    fn new(cc: &eframe::CreationContext<'_>) -> Self {
        apply_theme(&cc.egui_ctx);
        let (
            hybrid_engine,
            load_error,
            honesty,
            training_source,
            model_banner,
            model_name,
            metrics_lines,
            param_rows,
            precision_pm,
            precision_note,
            onnx_path_display,
        ) = match HybridEngine::load_default() {
            Ok(eng) => {
                let path = format!(
                    "{} + {}",
                    eng.baseline_path.display(),
                    eng.delta_path.display()
                );
                let h = eng
                    .baseline
                    .meta
                    .honesty
                    .clone()
                    .unwrap_or_else(|| "HYBRID_SCREENING".into());
                let banner = format!(
                    "hybrid live ONNX · baseline={} · delta={} · IdealLoads+COP screening",
                    eng.baseline.meta.champion.as_deref().unwrap_or("?"),
                    eng.delta.meta.champion.as_deref().unwrap_or("?")
                );
                let name = format!(
                    "hybrid {}+{}",
                    eng.baseline.meta.champion.as_deref().unwrap_or("base"),
                    eng.delta.meta.champion.as_deref().unwrap_or("delta")
                );
                (
                    Some(eng),
                    None,
                    h,
                    "notebook_hybrid_15min".into(),
                    banner,
                    name,
                    vec![
                        "Live 96-step hybrid from UI inputs (not static JSON alone)".into(),
                        "Honesty: HYBRID_SCREENING · IdealLoads+COP ≠ GSHP plant".into(),
                    ],
                    Vec::new(),
                    0.0,
                    "Promote gates require held-out recursive metrics; smoke farm needs VIBE22_ALLOW_SMOKE_PROMOTE=1"
                        .into(),
                    path,
                )
            }
            Err(e) => (
                None,
                Some(format!("Failed to load hybrid ONNX pair: {e:#}")),
                String::new(),
                String::new(),
                "no hybrid models loaded".into(),
                "—".into(),
                Vec::new(),
                Vec::new(),
                0.0,
                String::new(),
                "(missing real_baseline_15min_v1 + eplus_delta_15min_v1)".into(),
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
            hybrid_engine,
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
            midnight_facility_kw: 45.0,
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
            hybrid_walk: None,
            hybrid_path: None,
            hybrid_error: None,
            ship_walk: None,
            ship_path: None,
            status: "Tariff defaults = Creekside CP-2. Run live hybrid 96-step from UI inputs."
                .into(),
        };
        match load_hybrid_walk() {
            Ok((walk, path)) => {
                app.ship_path = Some(path.clone());
                app.ship_walk = Some(walk.clone());
                // Prefer live engine; keep ship walk as compare fallback until first Run.
                if app.hybrid_engine.is_none() {
                    app.hybrid_path = Some(path);
                    app.hybrid_walk = Some(walk);
                    app.status = format!(
                        "Precomputed ship walk only (no live ONNX). Peak Δ {:.1} kW.",
                        app.hybrid_walk.as_ref().unwrap().summary.delta_peak_kw
                    );
                } else {
                    app.status = format!(
                        "Hybrid ONNX loaded. Ship walk available for compare (Δpeak {:.1} kW).",
                        walk.summary.delta_peak_kw
                    );
                }
            }
            Err(e) => {
                if app.hybrid_engine.is_none() {
                    app.hybrid_error = Some(format!("{e:#}"));
                }
            }
        }

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

    /// Live hybrid 96-step from UI midnight state + weather + strategy.
    fn run_live_hybrid(&mut self, force_247_as_dsm: bool) -> bool {
        if self.hybrid_engine.is_none() {
            self.status = self
                .load_error
                .clone()
                .unwrap_or_else(|| "No hybrid ONNX loaded (hourly path quarantined)".into());
            return false;
        }
        let oat24: [f32; 24] = std::array::from_fn(|h| self.oat_at(h));
        let oat96 = expand_oat_24_to_96(&oat24);
        // Labeled fallbacks — not imported 96-step forecast
        let weather_mode = "oat_24_expanded_piecewise_constant;rh_ghi_labeled_fallback";
        let rh96 = [55.0_f32; STEPS_96];
        let mut ghi96 = [0.0_f32; STEPS_96];
        for step in 0..STEPS_96 {
            let h = step / 4;
            ghi96[step] = if (8..17).contains(&h) { 200.0 } else { 0.0 };
        }
        let sid = STRATEGY_IDS[self.strategy_idx].to_string();
        let month = self.month;
        let doy = self.doy;
        let weekend = if self.is_weekend { 1.0 } else { 0.0 };
        let init_kw = self.midnight_facility_kw;
        let zones = self.midnight_zone_f;

        let eng = self.hybrid_engine.as_mut().unwrap();
        match eng.rollout(
            init_kw,
            zones,
            &oat96,
            &rh96,
            &ghi96,
            month,
            doy,
            weekend,
            &sid,
            force_247_as_dsm,
        ) {
            Ok(mut walk) => {
                walk.weather_mode = Some(weather_mode.into());
                // Energy-preserving hourly means for charts; tariff uses true 96-step Σ(kW×0.25) + max demand
                let mut kw96 = [0.0_f32; STEPS_96];
                for (i, st) in walk.steps.iter().enumerate() {
                    kw96[i] = st.hybrid_facility_kw as f32;
                }
                let hourly = hourly_mean_from_quarters(&kw96);
                let month_u8 = month as u8;
                let cost = cost_day_tod_96(
                    &kw96,
                    &self.tariff,
                    self.is_weekend,
                    month_u8,
                    false,
                );
                if force_247_as_dsm {
                    self.pred_kw_compare = hourly;
                    self.compare_label = "HVAC 24/7 (live hybrid)".into();
                    self.cost_compare = Some(cost);
                } else {
                    self.pred_kw_dsm = hourly;
                    self.dsm_label = sid.clone();
                    self.cost_dsm = Some(cost);
                }
                let flag = walk
                    .outcome_flag
                    .clone()
                    .unwrap_or_else(|| "ok".into());
                self.status = format!(
                    "Live hybrid OK — peak {:.1}→{:.1} (Δ{:.1}) · {} · {} · {}",
                    walk.summary.peak_kw_baseline,
                    walk.summary.peak_kw_hybrid,
                    walk.summary.delta_peak_kw,
                    flag,
                    walk.honesty,
                    weather_mode
                );
                self.hybrid_path = Some(std::path::PathBuf::from("live_onnx"));
                self.hybrid_walk = Some(walk);
                self.hybrid_error = None;
                true
            }
            Err(e) => {
                self.status = format!("Live hybrid failed: {e:#}");
                false
            }
        }
    }

    fn run_compare_247_vs_dsm(&mut self) {
        // Baseline arm uses strategy baseline controls; DSM arm uses selected strategy.
        // Compare chart: run flat_24_7 as DSM-side for left bar, then real DSM.
        if !self.run_live_hybrid(true) {
            return;
        }
        let compare_walk = self.hybrid_walk.clone();
        if !self.run_live_hybrid(false) {
            return;
        }
        // Restore compare from 24/7 walk: hourly means for charts; 96-step tariff for demand/energy
        if let Some(w) = compare_walk {
            let mut kw96 = [0.0_f32; STEPS_96];
            for (i, st) in w.steps.iter().enumerate() {
                kw96[i] = st.hybrid_facility_kw as f32;
            }
            self.pred_kw_compare = hourly_mean_from_quarters(&kw96);
            self.compare_label = "HVAC 24/7 (live hybrid)".into();
            self.cost_compare = Some(cost_day_tod_96(
                &kw96,
                &self.tariff,
                self.is_weekend,
                self.month as u8,
                false,
            ));
        }
        self.refresh_annual();
        let pc = self
            .cost_compare
            .as_ref()
            .map(|c| c.peak_kw)
            .unwrap_or(0.0);
        let pd = self.cost_dsm.as_ref().map(|c| c.peak_kw).unwrap_or(0.0);
        self.status = format!(
            "Live compare OK — 24/7 peak {:.1} vs DSM {:.1} (Δpeak {:.1} kW)",
            pc,
            pd,
            (pc - pd).max(0.0)
        );
    }

    fn run_dsm_only(&mut self) {
        if !self.run_live_hybrid(false) {
            return;
        }
        if self.pred_kw_compare.iter().all(|v| *v == 0.0) {
            self.pred_kw_compare = self.pred_kw_dsm;
            self.compare_label = self.dsm_label.clone();
            self.cost_compare = self.cost_dsm.clone();
        }
        self.refresh_annual();
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
            if let Some(err) = &self.hybrid_error {
                ui.colored_label(
                    egui::Color32::from_rgb(230, 80, 80),
                    format!("Hybrid fail-closed: {err}"),
                );
            } else if self.hybrid_walk.is_some() {
                ui.colored_label(
                    egui::Color32::from_rgb(140, 200, 160),
                    "Hybrid 96-step walk loaded (HYBRID_SCREENING)",
                );
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
                                egui::RichText::new("▶  Live hybrid: 24/7 vs DSM")
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
                        .add_sized(
                            [340.0, 28.0],
                            egui::Button::new("Run live hybrid DSM (96-step)"),
                        )
                        .clicked()
                    {
                        self.run_dsm_only();
                    }
                    ui.label(
                        egui::RichText::new(&self.status)
                            .color(egui::Color32::from_rgb(180, 200, 190)),
                    );

                    ui.collapsing("Midnight measured state (required)", |ui| {
                        ui.label("Lag init = measured midnight — never hardcoded 35 kW / 80°F.");
                        ui.add(
                            egui::Slider::new(&mut self.midnight_facility_kw, 5.0..=200.0)
                                .text("facility kW @ midnight"),
                        );
                        for z in 0..6 {
                            ui.add(
                                egui::Slider::new(&mut self.midnight_zone_f[z], 50.0..=75.0)
                                    .text(ZONE_LABELS[z]),
                            );
                        }
                    });
                    if let Some(ship) = &self.ship_walk {
                        ui.collapsing("Precomputed ship walk (compare only)", |ui| {
                            ui.label(format!(
                                "Ship Δpeak {:.1} kW · not driven by UI until you Run live",
                                ship.summary.delta_peak_kw
                            ));
                            if let Some(p) = &self.ship_path {
                                ui.label(format!("{}", p.display()));
                            }
                        });
                    }
                });
            });

        egui::CentralPanel::default().show(ctx, |ui| {
            egui::ScrollArea::vertical().show(ui, |ui| {
                egui::CollapsingHeader::new("Hybrid Real+E+ 96-step DSM")
                    .default_open(true)
                    .show(ui, |ui| {
                        if let (Some(walk), Some(path)) =
                            (self.hybrid_walk.as_ref(), self.hybrid_path.as_ref())
                        {
                            show_hybrid_panel(ui, walk, path);
                        } else if let Some(err) = &self.hybrid_error {
                            ui.colored_label(egui::Color32::from_rgb(230, 80, 80), err);
                            ui.label(
                                "Promote hybrid artifacts via scripts/promote_hybrid_ship.py after training.",
                            );
                        }
                    });
                ui.add_space(8.0);
                egui::CollapsingHeader::new("Measured vs modeled validation")
                    .default_open(false)
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
