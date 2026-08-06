//! 15-min multitarget feature contract matching `ml/feature_compile_15min.py`.

pub const N_FEATURES_15MIN_MT: usize = 46;
pub const N_OUTPUTS: usize = 7;
pub const STEPS_96: usize = 96;

pub const ZONE_TEMP_COLS: [&str; 6] = [
    "zone_temp_1F_A_f",
    "zone_temp_1F_B_f",
    "zone_temp_1F_C_f",
    "zone_temp_1F_D_f",
    "zone_temp_2F_A_f",
    "zone_temp_2F_B_f",
];

pub const OCC_FRAC_COLS: [&str; 6] = [
    "occ_frac_1F_A",
    "occ_frac_1F_B",
    "occ_frac_1F_C",
    "occ_frac_1F_D",
    "occ_frac_2F_A",
    "occ_frac_2F_B",
];

pub const HP_ON_COLS: [&str; 6] = [
    "hp_on_1F_A",
    "hp_on_1F_B",
    "hp_on_1F_C",
    "hp_on_1F_D",
    "hp_on_2F_A",
    "hp_on_2F_B",
];

pub const STRATEGY_IDS_15: [&str; 5] = [
    "baseline",
    "stagger_preheat",
    "flat_24_7",
    "deep_setback",
    "morning_all_on",
];

/// Ordered feature columns — must match Python FEATURE_COLS_15MIN_MT.
pub const FEATURE_COLS_15MIN_MT: [&str; N_FEATURES_15MIN_MT] = [
    "step_15",
    "sin_step",
    "cos_step",
    "hour_ending",
    "month",
    "doy",
    "is_weekend",
    "occupied",
    "oat_f",
    "oat_lag1",
    "hdd65",
    "hdd65_cum_night",
    "hours_to_occupy",
    "rh_pct",
    "ghi",
    "occ_frac_1F_A",
    "occ_frac_1F_B",
    "occ_frac_1F_C",
    "occ_frac_1F_D",
    "occ_frac_2F_A",
    "occ_frac_2F_B",
    "hp_on_1F_A",
    "hp_on_1F_B",
    "hp_on_1F_C",
    "hp_on_1F_D",
    "hp_on_2F_A",
    "hp_on_2F_B",
    "sum_occ_frac",
    "sum_hp_on",
    "preheat_lead_h",
    "stagger_min",
    "unocc_htg_sp_f",
    "occ_htg_sp_f",
    "facility_kw_lag1",
    "facility_kw_lag2",
    "strategy_baseline",
    "strategy_stagger_preheat",
    "strategy_flat_24_7",
    "strategy_deep_setback",
    "strategy_morning_all_on",
    "zone_temp_1F_A_f_lag1",
    "zone_temp_1F_B_f_lag1",
    "zone_temp_1F_C_f_lag1",
    "zone_temp_1F_D_f_lag1",
    "zone_temp_2F_A_f_lag1",
    "zone_temp_2F_B_f_lag1",
];

#[derive(Clone, Debug, Default)]
pub struct RowMap {
    pub values: std::collections::BTreeMap<String, f32>,
}

impl RowMap {
    pub fn set(&mut self, k: &str, v: f32) {
        self.values.insert(k.to_string(), v);
    }

    pub fn get(&self, k: &str) -> f32 {
        *self.values.get(k).unwrap_or(&0.0)
    }

    pub fn to_feature_vec(&self, cols: &[String]) -> Vec<f32> {
        cols.iter().map(|c| self.get(c)).collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn feature_count_matches_contract() {
        assert_eq!(FEATURE_COLS_15MIN_MT.len(), N_FEATURES_15MIN_MT);
        assert_eq!(FEATURE_COLS_15MIN_MT.len(), 46);
    }
}
