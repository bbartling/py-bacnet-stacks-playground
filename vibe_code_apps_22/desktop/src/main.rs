//! Lakeside heating DSM desktop walk — egui + ONNX.
//!
//! Engineering cost inputs: $/kWh energy + $/kW demand (+ annual stub).
//! Model trained on ENERGYPLUS_SIMULATED farm when available.

mod features;
mod model;

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
            .with_inner_size([1180.0, 780.0])
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

    // Engineering rates (PLACEHOLDER defaults)
    energy_rate_per_kwh: f32,
    demand_rate_per_kw: f32,
    similar_days_per_year: f32,

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
            // cold winter day shape ~ 18°F mean, ±8°F diurnal
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

        Self {
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
            pred_kw: [0.0; 24],
            cost: None,
            status: "Set rates / HP grid, then Run 24h walk.".into(),
        }
    }

    fn oat_at(&self, hour: usize) -> f32 {
        if self.use_manual_oat {
            self.oat_manual[hour]
        } else {
            // Diurnal: coldest near hour 6, warmest ~15
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
            "Walk OK — ΣkWh={energy:.1}  peak={peak:.1} kW  source={}",
            self.training_source
        );
    }
}

impl eframe::App for DsmApp {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        egui::TopBottomPanel::top("banner").show(ctx, |ui| {
            ui.horizontal(|ui| {
                ui.heading("Lakeside Heating DSM");
                ui.separator();
                ui.label(format!("ML source: {}", self.training_source));
            });
            if !self.honesty.is_empty() {
                ui.colored_label(egui::Color32::from_rgb(180, 120, 40), &self.honesty);
            }
            if let Some(err) = &self.load_error {
                ui.colored_label(egui::Color32::RED, err);
            }
        });

        egui::SidePanel::left("controls")
            .default_width(340.0)
            .show(ctx, |ui| {
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
                        .max_height(120.0)
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
                ui.label("Display / B2 warm-by-start placeholder — kW model only today.");
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
                        egui::ScrollArea::vertical().max_height(200.0).show(ui, |ui| {
                            ui.horizontal(|ui| {
                                ui.label("HE");
                                for z in ZONE_LABELS {
                                    ui.label(z);
                                }
                            });
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
                ui.heading("Engineering rates");
                ui.label("PLACEHOLDER — not customer tariff until wired.");
                ui.add(
                    egui::DragValue::new(&mut self.energy_rate_per_kwh)
                        .speed(0.005)
                        .range(0.0..=2.0)
                        .prefix("$")
                        .suffix(" /kWh"),
                );
                ui.add(
                    egui::DragValue::new(&mut self.demand_rate_per_kw)
                        .speed(0.5)
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
                    .add_sized([280.0, 36.0], egui::Button::new("▶ Run 24h ONNX walk"))
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
                .height(280.0)
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
                ui.label("Run a walk to see $/kWh + $/kW costs.");
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
