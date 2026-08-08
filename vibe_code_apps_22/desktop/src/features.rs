//! Feature vector builder matching `ml/feature_compile_heating_dsm.py` FEATURE_COLS (39).

pub const N_FEATURES: usize = 39;
pub const ZONE_LABELS: [&str; 6] = ["1F-A", "1F-B", "1F-C", "1F-D", "2F-A", "2F-B"];

pub const STRATEGY_IDS: [&str; 5] = [
    "baseline",
    "stagger_preheat",
    "flat_24_7",
    "deep_setback",
    "morning_all_on",
];

#[derive(Clone, Debug)]
pub struct StrategyKnobs {
    pub preheat_lead_h: f32,
    pub stagger_min: f32,
    pub unocc_htg_sp_f: f32,
    pub occ_htg_sp_f: f32,
}

impl StrategyKnobs {
    pub fn for_id(sid: &str) -> Self {
        match sid {
            "stagger_preheat" => Self {
                preheat_lead_h: 2.0,
                stagger_min: 30.0,
                unocc_htg_sp_f: 64.0,
                occ_htg_sp_f: 68.0,
            },
            "flat_24_7" => Self {
                preheat_lead_h: 0.0,
                stagger_min: 0.0,
                unocc_htg_sp_f: 68.0,
                occ_htg_sp_f: 68.0,
            },
            "deep_setback" => Self {
                preheat_lead_h: 0.0,
                stagger_min: 0.0,
                unocc_htg_sp_f: 60.0,
                occ_htg_sp_f: 68.0,
            },
            "morning_all_on" => Self {
                preheat_lead_h: 2.0,
                stagger_min: 0.0,
                unocc_htg_sp_f: 62.0,
                occ_htg_sp_f: 68.0,
            },
            _ => Self {
                preheat_lead_h: 0.0,
                stagger_min: 0.0,
                unocc_htg_sp_f: 65.0,
                occ_htg_sp_f: 68.0,
            },
        }
    }
}

/// Default K12-ish occupancy fraction by hour and strategy (weekday).
pub fn default_occ_frac(hour: usize, strategy_id: &str, weekend: bool) -> [f32; 6] {
    if weekend {
        return [0.0; 6];
    }
    match strategy_id {
        "flat_24_7" => [1.0; 6],
        "morning_all_on" => {
            if (5..16).contains(&hour) {
                [1.0; 6]
            } else {
                [0.0; 6]
            }
        }
        "deep_setback" => {
            if (7..16).contains(&hour) {
                [1.0; 6]
            } else {
                [0.0; 6]
            }
        }
        "stagger_preheat" => {
            if hour >= 8 && hour < 16 {
                [1.0; 6]
            } else if !(5..8).contains(&hour) {
                [0.0; 6]
            } else {
                let n_on = ((hour as i32 - 4).max(0) as usize).min(6);
                let mut o = [0.0_f32; 6];
                for i in 0..n_on {
                    o[i] = 1.0;
                }
                if hour == 7 {
                    o = [0.85; 6];
                }
                o
            }
        }
        _ => {
            // baseline
            if (7..16).contains(&hour) {
                [1.0; 6]
            } else {
                [0.0; 6]
            }
        }
    }
}

pub struct HourInputs {
    pub hour_ending: f32,
    pub month: f32,
    pub doy: f32,
    pub is_weekend: f32,
    pub oat_f: f32,
    pub oat_lag1: f32,
    pub rh_pct: f32,
    pub ghi: f32,
    pub occ_frac: [f32; 6],
    pub hp_on: [f32; 6],
    pub knobs: StrategyKnobs,
    pub strategy_id: String,
    pub facility_kw_lag1: f32,
    pub facility_kw_lag2: f32,
    pub hdd65_cum_night: f32,
}

pub fn build_features(h: &HourInputs) -> [f32; N_FEATURES] {
    let he = h.hour_ending;
    let sin_hour = (2.0 * std::f32::consts::PI * he / 24.0).sin();
    let cos_hour = (2.0 * std::f32::consts::PI * he / 24.0).cos();
    let occupied = if h.is_weekend < 0.5 && (7.0..16.0).contains(&he) {
        1.0
    } else {
        0.0
    };
    let hdd65 = (65.0 - h.oat_f).max(0.0);
    let hours_to_occupy = if h.is_weekend >= 0.5 {
        24.0
    } else if he < 7.0 {
        7.0 - he
    } else if he >= 16.0 {
        24.0 - he + 7.0
    } else {
        0.0
    };
    let sum_occ: f32 = h.occ_frac.iter().sum();
    let sum_hp: f32 = h.hp_on.iter().sum();

    let mut f = [0.0_f32; N_FEATURES];
    f[0] = he;
    f[1] = sin_hour;
    f[2] = cos_hour;
    f[3] = h.month;
    f[4] = h.doy;
    f[5] = h.is_weekend;
    f[6] = occupied;
    f[7] = h.oat_f;
    f[8] = h.oat_lag1;
    f[9] = hdd65;
    f[10] = h.hdd65_cum_night;
    f[11] = hours_to_occupy;
    f[12] = h.rh_pct;
    f[13] = h.ghi;
    for i in 0..6 {
        f[14 + i] = h.occ_frac[i];
    }
    for i in 0..6 {
        f[20 + i] = h.hp_on[i];
    }
    f[26] = sum_occ;
    f[27] = sum_hp;
    f[28] = h.knobs.preheat_lead_h;
    f[29] = h.knobs.stagger_min;
    f[30] = h.knobs.unocc_htg_sp_f;
    f[31] = h.knobs.occ_htg_sp_f;
    f[32] = h.facility_kw_lag1;
    f[33] = h.facility_kw_lag2;
    // strategy one-hots at indices 34..38
    for (i, sid) in STRATEGY_IDS.iter().enumerate() {
        f[34 + i] = if *sid == h.strategy_id.as_str() {
            1.0
        } else {
            0.0
        };
    }
    f
}

pub fn scale_features(raw: &[f32; N_FEATURES], mean: &[f32], scale: &[f32]) -> [f32; N_FEATURES] {
    let mut out = [0.0_f32; N_FEATURES];
    for i in 0..N_FEATURES {
        let s = if scale[i].abs() < 1e-12 {
            1.0
        } else {
            scale[i]
        };
        out[i] = (raw[i] - mean[i]) / s;
    }
    out
}

#[derive(Clone, Debug)]
pub struct DayCost {
    pub energy_kwh: f32,
    pub peak_kw: f32,
    pub energy_cost: f32,
    pub demand_cost: f32,
    pub total_cost: f32,
    pub annual_energy_stub: f32,
    pub annual_demand_stub: f32,
    pub annual_total_stub: f32,
}

pub fn cost_from_hourly_kw(
    kw: &[f32],
    energy_rate_per_kwh: f32,
    demand_rate_per_kw: f32,
    similar_days_per_year: f32,
) -> DayCost {
    let energy_kwh: f32 = kw.iter().sum();
    let peak_kw = kw.iter().copied().fold(0.0_f32, f32::max);
    let energy_cost = energy_kwh * energy_rate_per_kwh;
    let demand_cost = peak_kw * demand_rate_per_kw;
    DayCost {
        energy_kwh,
        peak_kw,
        energy_cost,
        demand_cost,
        total_cost: energy_cost + demand_cost,
        annual_energy_stub: energy_cost * similar_days_per_year,
        annual_demand_stub: demand_cost * 12.0,
        annual_total_stub: energy_cost * similar_days_per_year + demand_cost * 12.0,
    }
}
