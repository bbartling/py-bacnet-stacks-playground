//! Portable demand + energy tariff (TOD-capable).
//!
//! Defaults are prefilled for Lakeside / Creekside CP-2 (June 2026 bill snippet)
//! but every field is editable so other utility tariffs can be entered.

use serde::{Deserialize, Serialize};

/// Generic commercial tariff with optional TOD energy and two demand channels.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct DemandTariff {
    pub label: String,
    /// Flat monthly customer / facilities charge [$/mo]
    pub customer_charge: f32,
    /// On-peak energy [$/kWh]
    pub energy_on_peak_per_kwh: f32,
    /// Off-peak energy [$/kWh]
    pub energy_off_peak_per_kwh: f32,
    /// Power cost adjustment / PCA adder applied to all kWh [$/kWh]
    pub pca_per_kwh: f32,
    /// Primary demand (generation / transmission) [$/kW]
    pub demand_per_kw: f32,
    /// Distribution / secondary demand [$/kW] (often ratchet / billed demand)
    pub distribution_demand_per_kw: f32,
    /// Inclusive hour-ending start of weekday on-peak (local)
    pub on_peak_he_start: u8,
    /// Exclusive hour-ending end of weekday on-peak (local)
    pub on_peak_he_end: u8,
    /// When true, weekends are entirely off-peak
    pub weekends_off_peak: bool,
    /// Optional step-up rates (e.g. Aug+) — used when `use_step_up` is true
    pub demand_per_kw_step: f32,
    pub distribution_demand_per_kw_step: f32,
    pub step_up_from_month: u8,
    pub use_step_up: bool,
    /// Honesty / source note shown in UI
    pub honesty: String,
}

impl Default for DemandTariff {
    fn default() -> Self {
        creekside_cp2_defaults()
    }
}

/// Prefill from Creekside June CP-2 snippet + Aug rate step noted by client.
pub fn creekside_cp2_defaults() -> DemandTariff {
    DemandTariff {
        label: "Creekside CP-2 (Small Power TOD) — editable".into(),
        customer_charge: 200.0,
        energy_on_peak_per_kwh: 0.075,
        energy_off_peak_per_kwh: 0.050,
        pca_per_kwh: 0.0034,
        demand_per_kw: 12.0,
        distribution_demand_per_kw: 1.50,
        on_peak_he_start: 8,
        on_peak_he_end: 20,
        weekends_off_peak: true,
        demand_per_kw_step: 12.25,
        distribution_demand_per_kw_step: 1.75,
        step_up_from_month: 8,
        use_step_up: true,
        honesty: (
            "Defaults from Creekside June CP-2 bill snippet (on/off-peak energy, \
             $12/kW demand + $1.50/kW distribution). Aug+ step $12.25/$1.75 enabled. \
             On-peak HE 08–20 weekdays is an engineering assumption — edit for your tariff. \
             CANDIDATE playground — not a bill replica."
        )
        .into(),
    }
}

impl DemandTariff {
    pub fn demand_rate_for_month(&self, month: u8) -> f32 {
        if self.use_step_up && month >= self.step_up_from_month {
            self.demand_per_kw_step
        } else {
            self.demand_per_kw
        }
    }

    pub fn distribution_rate_for_month(&self, month: u8) -> f32 {
        if self.use_step_up && month >= self.step_up_from_month {
            self.distribution_demand_per_kw_step
        } else {
            self.distribution_demand_per_kw
        }
    }

    pub fn is_on_peak(&self, hour_ending: usize, weekend: bool) -> bool {
        if weekend && self.weekends_off_peak {
            return false;
        }
        let h = hour_ending as u8;
        h >= self.on_peak_he_start && h < self.on_peak_he_end
    }
}

#[derive(Clone, Debug, Default)]
pub struct TodDayCost {
    pub energy_kwh: f32,
    pub on_peak_kwh: f32,
    pub off_peak_kwh: f32,
    pub peak_kw: f32,
    pub energy_on_peak_cost: f32,
    pub energy_off_peak_cost: f32,
    pub pca_cost: f32,
    pub demand_cost: f32,
    pub distribution_demand_cost: f32,
    pub customer_charge_day_share: f32,
    pub total_cost: f32,
}

/// Cost one 24h profile under a portable TOD + dual-demand tariff.
pub fn cost_day_tod(
    kw: &[f32; 24],
    tariff: &DemandTariff,
    weekend: bool,
    month: u8,
    include_customer_day_share: bool,
) -> TodDayCost {
    let mut on_kwh = 0.0_f32;
    let mut off_kwh = 0.0_f32;
    for h in 0..24 {
        let e = kw[h].max(0.0);
        if tariff.is_on_peak(h, weekend) {
            on_kwh += e;
        } else {
            off_kwh += e;
        }
    }
    let energy_kwh = on_kwh + off_kwh;
    let peak_kw = kw.iter().copied().fold(0.0_f32, f32::max);
    let energy_on = on_kwh * tariff.energy_on_peak_per_kwh;
    let energy_off = off_kwh * tariff.energy_off_peak_per_kwh;
    let pca = energy_kwh * tariff.pca_per_kwh;
    let d_rate = tariff.demand_rate_for_month(month);
    let dist_rate = tariff.distribution_rate_for_month(month);
    let demand_cost = peak_kw * d_rate;
    // Day playground: apply distribution demand to same-day peak (annual rollup uses billed demand)
    let distribution_demand_cost = peak_kw * dist_rate;
    let cust = if include_customer_day_share {
        tariff.customer_charge / 30.0
    } else {
        0.0
    };
    TodDayCost {
        energy_kwh,
        on_peak_kwh: on_kwh,
        off_peak_kwh: off_kwh,
        peak_kw,
        energy_on_peak_cost: energy_on,
        energy_off_peak_cost: energy_off,
        pca_cost: pca,
        demand_cost,
        distribution_demand_cost,
        customer_charge_day_share: cust,
        total_cost: energy_on + energy_off + pca + demand_cost + distribution_demand_cost + cust,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn creekside_tod_split_and_aug_step() {
        let t = creekside_cp2_defaults();
        assert!(t.is_on_peak(12, false));
        assert!(!t.is_on_peak(12, true));
        assert!(!t.is_on_peak(3, false));
        assert!((t.demand_rate_for_month(6) - 12.0).abs() < 1e-6);
        assert!((t.demand_rate_for_month(8) - 12.25).abs() < 1e-6);
        let mut kw = [10.0_f32; 24];
        kw[14] = 50.0;
        let c = cost_day_tod(&kw, &t, false, 6, false);
        assert!((c.peak_kw - 50.0).abs() < 1e-4);
        assert!(c.on_peak_kwh > 0.0 && c.off_peak_kwh > 0.0);
        assert!((c.demand_cost - 50.0 * 12.0).abs() < 1e-2);
    }
}
