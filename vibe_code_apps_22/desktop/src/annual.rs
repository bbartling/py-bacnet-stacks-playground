//! Annual demand / energy savings rollup from monthly bill peaks + day walks.

use crate::tariff::DemandTariff;
use serde::Deserialize;
use std::path::Path;

#[derive(Clone, Debug, Deserialize)]
pub struct MonthlyPeakRow {
    pub month: String,
    #[serde(default)]
    pub billing_period: Option<i64>,
    #[serde(default)]
    pub kwh: Option<f32>,
    #[serde(default)]
    pub cost_usd: Option<f32>,
    #[serde(default)]
    pub demand_kw: Option<f32>,
    #[serde(default)]
    pub billed_demand_kw: Option<f32>,
    #[serde(default)]
    pub days: Option<f32>,
}

#[derive(Clone, Debug)]
pub struct MonthlyBook {
    pub rows: Vec<MonthlyPeakRow>,
    pub path: String,
}

impl MonthlyBook {
    pub fn load_csv(path: &Path) -> anyhow::Result<Self> {
        let mut rdr = csv::Reader::from_path(path)?;
        let mut rows = Vec::new();
        for rec in rdr.deserialize() {
            let row: MonthlyPeakRow = rec?;
            rows.push(row);
        }
        if rows.is_empty() {
            anyhow::bail!("no monthly rows in {}", path.display());
        }
        Ok(Self {
            rows,
            path: path.display().to_string(),
        })
    }

    pub fn max_demand_kw(&self) -> f32 {
        self.rows
            .iter()
            .filter_map(|r| r.demand_kw)
            .fold(0.0_f32, f32::max)
    }

    pub fn max_billed_demand_kw(&self) -> f32 {
        self.rows
            .iter()
            .filter_map(|r| r.billed_demand_kw)
            .fold(0.0_f32, f32::max)
    }
}

#[derive(Clone, Debug, Default)]
pub struct AnnualRollup {
    pub months_used: usize,
    pub baseline_demand_cost: f32,
    pub dsm_demand_cost: f32,
    pub baseline_dist_cost: f32,
    pub dsm_dist_cost: f32,
    pub demand_savings: f32,
    pub dist_savings: f32,
    pub energy_penalty: f32,
    pub net_annual_savings: f32,
    pub delta_peak_kw: f32,
    pub delta_kwh_day: f32,
    pub similar_cold_days: f32,
    pub ratchet_months_shaved: usize,
    pub note: String,
}

fn month_num(s: &str) -> u8 {
    // "2026-05" or "2026-5"
    let parts: Vec<&str> = s.split('-').collect();
    if parts.len() >= 2 {
        parts[1].parse::<u8>().unwrap_or(1)
    } else if let Some(bp) = s.parse::<i64>().ok() {
        (bp % 100) as u8
    } else {
        1
    }
}

/// Heuristic annual savings from workbook peaks + one-day walk deltas.
///
/// - Shaves each month's `demand_kw` by `delta_peak_kw` (floor 0)
/// - Shaves `billed_demand_kw` only in months within `ratchet_tol_kw` of the annual
///   billed-demand max (conservative ratchet proxy)
/// - Energy: `delta_kwh_day * similar_cold_days` valued at blended on/off mix
pub fn rollup_annual_savings(
    book: &MonthlyBook,
    tariff: &DemandTariff,
    delta_peak_kw: f32,
    delta_kwh_day: f32,
    similar_cold_days: f32,
    on_peak_energy_share: f32,
    ratchet_tol_kw: f32,
) -> AnnualRollup {
    let max_billed = book.max_billed_demand_kw();
    let shave = delta_peak_kw.max(0.0);
    let share = on_peak_energy_share.clamp(0.0, 1.0);

    let mut base_d = 0.0_f32;
    let mut dsm_d = 0.0_f32;
    let mut base_dist = 0.0_f32;
    let mut dsm_dist = 0.0_f32;
    let mut ratchet_n = 0usize;
    let mut n = 0usize;

    for row in &book.rows {
        let Some(demand) = row.demand_kw else {
            continue;
        };
        let billed = row.billed_demand_kw.unwrap_or(demand);
        let m = month_num(&row.month);
        let d_rate = tariff.demand_rate_for_month(m);
        let dist_rate = tariff.distribution_rate_for_month(m);

        base_d += demand * d_rate;
        let dsm_demand = (demand - shave).max(0.0);
        dsm_d += dsm_demand * d_rate;

        base_dist += billed * dist_rate;
        let near_ratchet = (max_billed - billed).abs() <= ratchet_tol_kw || billed >= max_billed - 1e-3;
        let dsm_billed = if near_ratchet && shave > 0.0 {
            ratchet_n += 1;
            (billed - shave).max(0.0)
        } else {
            billed
        };
        dsm_dist += dsm_billed * dist_rate;
        n += 1;
    }

    let blended = share * tariff.energy_on_peak_per_kwh
        + (1.0 - share) * tariff.energy_off_peak_per_kwh
        + tariff.pca_per_kwh;
    // Positive delta_kwh_day means DSM used MORE energy → penalty
    let energy_penalty = delta_kwh_day * similar_cold_days * blended;

    let demand_savings = base_d - dsm_d;
    let dist_savings = base_dist - dsm_dist;
    let net = demand_savings + dist_savings - energy_penalty;

    AnnualRollup {
        months_used: n,
        baseline_demand_cost: base_d,
        dsm_demand_cost: dsm_d,
        baseline_dist_cost: base_dist,
        dsm_dist_cost: dsm_dist,
        demand_savings,
        dist_savings,
        energy_penalty,
        net_annual_savings: net,
        delta_peak_kw: shave,
        delta_kwh_day,
        similar_cold_days,
        ratchet_months_shaved: ratchet_n,
        note: format!(
            "Heuristic from {} months in {}. Demand shaved every month by Δpeak; \
             billed/distribution demand shaved only near annual max (tol {:.1} kW). \
             Energy penalty = ΔkWh/day × {:.0} similar cold days × blended rate. \
             Not a full 8760 / ratchet-clause engine.",
            n,
            book.path,
            ratchet_tol_kw,
            similar_cold_days
        ),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::tariff::creekside_cp2_defaults;

    #[test]
    fn rollup_positive_when_peak_shaved() {
        let book = MonthlyBook {
            path: "test".into(),
            rows: vec![
                MonthlyPeakRow {
                    month: "2025-01".into(),
                    billing_period: None,
                    kwh: Some(1000.0),
                    cost_usd: None,
                    demand_kw: Some(200.0),
                    billed_demand_kw: Some(280.0),
                    days: Some(31.0),
                },
                MonthlyPeakRow {
                    month: "2025-06".into(),
                    billing_period: None,
                    kwh: Some(800.0),
                    cost_usd: None,
                    demand_kw: Some(170.0),
                    billed_demand_kw: Some(287.0),
                    days: Some(30.0),
                },
            ],
        };
        let t = creekside_cp2_defaults();
        let r = rollup_annual_savings(&book, &t, 20.0, 50.0, 90.0, 0.55, 5.0);
        assert_eq!(r.months_used, 2);
        assert!(r.demand_savings > 0.0);
        assert!(r.dist_savings > 0.0);
        assert!(r.energy_penalty > 0.0);
    }
}
