//! Lakeside heating DSM desktop walk — egui + ONNX.
//!
//! Load utility bill CSV → validate columns → derive $/kWh + $/kW (OLS).
//! Model trained on ENERGYPLUS_SIMULATED farm when available.

mod bills;
mod features;
mod model;

use bills::{try_autoload_bills, BillBook, DerivedRates};
use eframe::egui;
use egui_plot::{Line, Plot, PlotPoints};
use features::{
    build_features, cost_from_hourly_kw, default_occ_frac, DayCost, HourInputs, StrategyKnobs,
    STRATEGY_IDS, ZONE_LABELS,
};
use model::{default_artifact_paths, OnnxModel};

fn main() -> eframe::Result<()> {
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([1220.0, 820.0])
            .with_title("Lakeside Heating DSM — ONNX walk"),
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

    // Day / weather
    month: f32,
    doy: f32,
    is_weekend: bool,
    oat_midnight_f: f32,
    oat_amplitude_f: f32,
    oat_manual: [f32; 24],
    use_manual_oat: bool,
    midnight_zone_f: [f32; 6],

    // Controls
    strategy_idx: usize,
    hp_on: [[bool; 6]; 24],
    use_strategy_occ: bool,
    occ_override: [[f32; 6]; 24],

    // Engineering rates (from bills when loaded)
    energy_rate_per_kwh: f32,
    demand_rate_per_kw: f32,
    similar_days_per_year: f32,
    rate_label: String,
    rate_honesty: String,

    // Utility bills
    bill_book: Option<BillBook>,
    bill_error: Option<String>,
    bill_warnings: Vec<String>,
    /// 0 = heating OLS, 1 = all-months OLS, 2+ = individual months
    rate_preset_idx: usize,

    // Results
    pred_kw: [f32; 24],
    cost: Option<DayCost>,
    status: String,
}

impl DsmApp {
    fn new(_cc: &eframe::CreationContext<'_>) -> Self {
        let (onnx, meta) = default_artifact_paths();
        let (model, load_error, honesty, training_source) = match OnnxModel::load(&onnx, &meta) {
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
                (Some(m), None, h, s)
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
            ),
        };

        let mut oat = [0.0_f32; 24];
        for h in 0..24 {
            oat[h] = 18.0 + 8.0 * ((h as f32 - 14.0) * std::f32::consts::PI / 12.0).sin();
        }

        let mut hp_on = [[false; 6]; 24];
        let mut occ = [[0.0_f32; 6]; 24];
        for h in 0..24 {
            let o = default_occ_frac(h, "baseline", false);
            occ[h] = o;
            for z in 0..6 {
                hp_on[h][z] = o[z] > 0.05;
            }
        }

        let mut app = Self {
            model,
            load_error,
            honesty,
            training_source,
            month: 1.0,
            doy: 15.0,
            is_weekend: false,
            oat_midnight_f: 15.0,
            oat_amplitude_f: 10.0,
            oat_manual: oat,
            use_manual_oat: true,
            midnight_zone_f: [62.0; 6],
            strategy_idx: 0,
            hp_on,
            use_strategy_occ: true,
            occ_override: occ,
            energy_rate_per_kwh: 0.12,
            demand_rate_per_kw: 15.0,
            similar_days_per_year: 90.0,
            rate_label: "PLACEHOLDER defaults".into(),
            rate_honesty: "No utility CSV loaded — using engineering placeholders ($0.12/kWh, $15/kW)."
                .into(),
            bill_book: None,
            bill_error: None,
            bill_warnings: Vec::new(),
            rate_preset_idx: 0,
            pred_kw: [0.0; 24],
            cost: None,
            status: "Load utility bills CSV (or auto-load sample), then Run 24h walk.".into(),
        };

        match try_autoload_bills() {
            Ok(Some(book)) => app.apply_bill_book(book),
            Ok(None) => {}
            Err(e) => {
                app.bill_error = Some(format!(
                    "Auto-load utility CSV failed (app still runs with placeholders):\n{}",
                    e.message
                ));
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
        self.status = format!(
            "Rates from {} — ${:.4}/kWh + ${:.2}/kW",
            self.rate_label, self.energy_rate_per_kwh, self.demand_rate_per_kw
        );
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
                self.status = format!(
                    "Loaded {} bill months from {}",
                    book.rows.len(),
                    book.path
                );
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
                    message: "Heating-season OLS unavailable (need ≥3 Nov–Mar months with demand)."
                        .into(),
                }),
            1 => book
                .all_months_ols
                .clone()
                .ok_or_else(|| bills::BillLoadError {
                    message: "All-months OLS unavailable (need ≥3 months).".into(),
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
            Err(e) => {
                self.bill_error = Some(e.message);
            }
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
                self.status = "Utility CSV rejected — rates unchanged.".into();
            }
        }
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

    fn run_walk(&mut self) {
        if self.model.is_none() {
            self.status = self
                .load_error
                .clone()
                .unwrap_or_else(|| "No model loaded".into());
            return;
        }

        let oat_profile: [f32; 24] = std::array::from_fn(|h| self.oat_at(h));
        let sid = STRATEGY_IDS[self.strategy_idx].to_string();
        let knobs = StrategyKnobs::for_id(&sid);
        let weekend = self.is_weekend;
        let use_strategy_occ = self.use_strategy_occ;
        let month = self.month;
        let doy = self.doy;
        let hp_on = self.hp_on;
        let occ_override = self.occ_override;

        let mut lag1 = 35.0_f32;
        let mut lag2 = 35.0_f32;
        let mut cum_hdd_night = 0.0_f32;
        let mut pred = [0.0_f32; 24];

        let model = self.model.as_mut().unwrap();

        for h in 0..24 {
            let oat = oat_profile[h];
            let oat_lag1 = if h == 0 {
                oat
            } else {
                oat_profile[h - 1]
            };
            let hdd = (65.0 - oat).max(0.0);
            if h < 5 || h >= 20 {
                cum_hdd_night += hdd;
            }

            let occ = if use_strategy_occ {
                default_occ_frac(h, &sid, weekend)
            } else {
                occ_override[h]
            };
            let mut hp = [0.0_f32; 6];
            for z in 0..6 {
                hp[z] = if hp_on[h][z] { 1.0 } else { 0.0 };
            }

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
                strategy_id: sid.clone(),
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
                    return;
                }
            }
        }

        self.pred_kw = pred;
        self.cost = Some(cost_from_hourly_kw(
            &pred,
            self.energy_rate_per_kwh,
            self.demand_rate_per_kw,
            self.similar_days_per_year,
        ));
        let peak = pred.iter().copied().fold(0.0_f32, f32::max);
        let energy: f32 = pred.iter().sum();
        self.status = format!(
            "Walk OK — ΣkWh={energy:.1}  peak={peak:.1} kW  rates={}  ML={}",
            self.rate_label, self.training_source
        );
    }
}

impl eframe::App for DsmApp {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        egui::TopBottomPanel::top("banner").show(ctx, |ui| {
            ui.horizontal(|ui| {
                ui.heading("Lakeside Heating DSM");
                ui.separator();
                ui.label(format!("ML: {}", self.training_source));
                ui.separator();
                ui.label(format!("Rates: {}", self.rate_label));
            });
            if !self.honesty.is_empty() {
                ui.colored_label(egui::Color32::from_rgb(180, 120, 40), &self.honesty);
            }
            if !self.rate_honesty.is_empty() {
                ui.colored_label(
                    egui::Color32::from_rgb(60, 100, 140),
                    &self.rate_honesty,
                );
            }
            if let Some(err) = &self.load_error {
                ui.colored_label(egui::Color32::RED, err);
            }
            if let Some(err) = &self.bill_error {
                ui.colored_label(
                    egui::Color32::from_rgb(200, 60, 60),
                    format!("Utility CSV: {err}"),
                );
            }
        });

        egui::SidePanel::left("controls")
            .default_width(360.0)
            .show(ctx, |ui| {
                ui.heading("Utility bills → rates");
                ui.label("Load a monthly bill CSV (canonical or utility-export aliases).");
                if ui
                    .add_sized([320.0, 28.0], egui::Button::new("📂 Load utility bills CSV…"))
                    .clicked()
                {
                    self.pick_and_load_bills();
                }
                if let Some(book) = &self.bill_book {
                    ui.label(format!("{} months · {}", book.rows.len(), book.path));
                    let prev = self.rate_preset_idx;
                    let mut labels: Vec<String> = vec![
                        "Heating season OLS (Nov–Mar)".into(),
                        "All months OLS".into(),
                    ];
                    for r in &book.rows {
                        labels.push(format!(
                            "Month {} ({:.0} kWh, ${:.0})",
                            r.month_key, r.kwh, r.cost_usd
                        ));
                    }
                    let selected = labels
                        .get(self.rate_preset_idx)
                        .cloned()
                        .unwrap_or_else(|| "(none)".into());
                    egui::ComboBox::from_label("Rate preset")
                        .selected_text(selected)
                        .width(280.0)
                        .show_ui(ui, |ui| {
                            for (i, lab) in labels.iter().enumerate() {
                                ui.selectable_value(&mut self.rate_preset_idx, i, lab);
                            }
                        });
                    if prev != self.rate_preset_idx {
                        self.apply_rate_preset();
                    }
                } else {
                    ui.weak("No bills loaded — placeholders active.");
                }
                for w in &self.bill_warnings {
                    ui.colored_label(egui::Color32::from_rgb(160, 120, 40), format!("⚠ {w}"));
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
                        .max_height(100.0)
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
                ui.heading("Midnight zone temps (°F)");
                ui.weak("B2 warm-by-start placeholder — kW model only today.");
                for z in 0..6 {
                    ui.add(
                        egui::Slider::new(&mut self.midnight_zone_f[z], 50.0..=75.0)
                            .text(ZONE_LABELS[z]),
                    );
                }

                ui.separator();
                ui.heading("Strategy / HP on");
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

                egui::CollapsingHeader::new("Per-hour zone HP on/off")
                    .default_open(false)
                    .show(ui, |ui| {
                        egui::ScrollArea::vertical().max_height(160.0).show(ui, |ui| {
                            for h in 0..24 {
                                ui.horizontal(|ui| {
                                    ui.label(format!("{h:02}"));
                                    for z in 0..6 {
                                        ui.checkbox(&mut self.hp_on[h][z], "");
                                    }
                                });
                            }
                        });
                    });

                ui.separator();
                ui.heading("Cost rates (editable)");
                ui.add(
                    egui::DragValue::new(&mut self.energy_rate_per_kwh)
                        .speed(0.001)
                        .range(0.0..=2.0)
                        .prefix("$")
                        .suffix(" /kWh"),
                );
                ui.add(
                    egui::DragValue::new(&mut self.demand_rate_per_kw)
                        .speed(0.25)
                        .range(0.0..=100.0)
                        .prefix("$")
                        .suffix(" /kW (day peak)"),
                );
                ui.add(
                    egui::DragValue::new(&mut self.similar_days_per_year)
                        .speed(1.0)
                        .range(1.0..=200.0)
                        .suffix(" similar cold days/yr"),
                );

                ui.separator();
                if ui
                    .add_sized([320.0, 36.0], egui::Button::new("▶ Run 24h ONNX walk"))
                    .clicked()
                {
                    self.run_walk();
                }
                ui.label(&self.status);
            });

        egui::CentralPanel::default().show(ctx, |ui| {
            ui.heading("Hourly facility kW");
            let points: PlotPoints = (0..24)
                .map(|h| [h as f64, self.pred_kw[h] as f64])
                .collect();
            Plot::new("kw_plot")
                .height(260.0)
                .legend(egui_plot::Legend::default())
                .show(ui, |plot_ui| {
                    plot_ui.line(Line::new(points).name("facility_kW"));
                });

            ui.separator();
            ui.heading("Cost playground");
            if let Some(c) = &self.cost {
                egui::Grid::new("cost_grid")
                    .num_columns(2)
                    .striped(true)
                    .show(ui, |ui| {
                        ui.label("Energy");
                        ui.label(format!("{:.1} kWh → ${:.2}", c.energy_kwh, c.energy_cost));
                        ui.end_row();
                        ui.label("Peak demand");
                        ui.label(format!("{:.1} kW → ${:.2}", c.peak_kw, c.demand_cost));
                        ui.end_row();
                        ui.label("Day total");
                        ui.strong(format!("${:.2}", c.total_cost));
                        ui.end_row();
                        ui.label("Annual energy stub");
                        ui.label(format!("${:.0}", c.annual_energy_stub));
                        ui.end_row();
                        ui.label("Annual demand stub (×12)");
                        ui.label(format!("${:.0}", c.annual_demand_stub));
                        ui.end_row();
                        ui.label("Annual total stub");
                        ui.strong(format!("${:.0}", c.annual_total_stub));
                        ui.end_row();
                    });
            } else {
                ui.label("Run a walk to see costs at the loaded bill rates.");
            }

            if let Some(book) = &self.bill_book {
                ui.separator();
                ui.collapsing("Loaded bill months", |ui| {
                    egui::Grid::new("bill_tbl").striped(true).show(ui, |ui| {
                        ui.label("Month");
                        ui.label("kWh");
                        ui.label("Demand");
                        ui.label("Billed");
                        ui.label("Cost $");
                        ui.end_row();
                        for r in &book.rows {
                            ui.label(&r.month_key);
                            ui.label(format!("{:.0}", r.kwh));
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
                            ui.label(format!("{:.0}", r.cost_usd));
                            ui.end_row();
                        }
                    });
                });
            }

            ui.separator();
            ui.collapsing("Hourly table", |ui| {
                egui::Grid::new("hour_tbl").striped(true).show(ui, |ui| {
                    ui.label("HE");
                    ui.label("OAT °F");
                    ui.label("kW");
                    ui.end_row();
                    for h in 0..24 {
                        ui.label(format!("{h:02}"));
                        ui.label(format!("{:.1}", self.oat_at(h)));
                        ui.label(format!("{:.1}", self.pred_kw[h]));
                        ui.end_row();
                    }
                });
            });
        });
    }
}
