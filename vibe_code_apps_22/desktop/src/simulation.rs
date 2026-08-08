//! Shared simulation contracts for hybrid ML and Nearest-Day engines.
//!
//! Optimization readiness (no general optimizer in this pass):
//! - `SimulationRequest` / `SimulationResult` are the stable API surface
//! - `ControlSchedule96` is the existing `ControlSchedule` (actual 96-step controls)
//! - Strategy enumeration ranks named strategies; not mathematical optimization
//! - Annual rollups remain HEURISTIC until Annual Replay exists

use crate::control_contract::{load_control_schedule, ControlSchedule};
use crate::features_15min::{STEPS_96, ZONE_TEMP_COLS};
use crate::nearest_day::billing_period_demand_kw;
use crate::tariff::DemandTariff;

/// Alias documenting the 96-step control contract used by engines.
pub type ControlSchedule96 = ControlSchedule;

/// Unsupported control for nearest-day E+ delta library (no arbitrary schedules).
pub const UNSUPPORTED_CONTROL_SCHEDULE: &str = "UNSUPPORTED_CONTROL_SCHEDULE";

/// Shared one-day simulation request (midnight state + weather + schedule + tariff).
#[derive(Debug, Clone)]
pub struct SimulationRequest {
    pub midnight_facility_kw: f32,
    pub midnight_zone_temps_f: [f32; 6],
    pub oat_f_96: [f32; STEPS_96],
    pub rh_pct_96: [f32; STEPS_96],
    pub ghi_96: [f32; STEPS_96],
    pub month: f32,
    pub doy: f32,
    pub is_weekend: bool,
    pub schedule: ControlSchedule96,
    pub tariff: DemandTariff,
    pub existing_billing_peak_kw: f32,
    /// Optional ratchet / billed-demand state (HEURISTIC until Annual Replay).
    pub billed_demand_kw: Option<f32>,
    pub honesty_note: String,
}

impl SimulationRequest {
    pub fn from_strategy_id(
        strategy_id: &str,
        midnight_facility_kw: f32,
        midnight_zone_temps_f: [f32; 6],
        oat_f_96: [f32; STEPS_96],
        month: f32,
        doy: f32,
        is_weekend: bool,
        tariff: DemandTariff,
        existing_billing_peak_kw: f32,
    ) -> anyhow::Result<Self> {
        let schedule = load_control_schedule(strategy_id)?;
        let rh_pct_96 = [55.0_f32; STEPS_96];
        let mut ghi_96 = [0.0_f32; STEPS_96];
        for step in 0..STEPS_96 {
            let h = step / 4;
            ghi_96[step] = if (8..17).contains(&h) { 200.0 } else { 0.0 };
        }
        Ok(Self {
            midnight_facility_kw,
            midnight_zone_temps_f,
            oat_f_96,
            rh_pct_96,
            ghi_96,
            month,
            doy,
            is_weekend,
            schedule,
            tariff,
            existing_billing_peak_kw,
            billed_demand_kw: None,
            honesty_note: "simulation request — screening / playground".into(),
        })
    }

    pub fn strategy_id(&self) -> &str {
        &self.schedule.strategy_id
    }
}

/// Shared one-day simulation result for ML hybrid and Nearest-Day engines.
#[derive(Debug, Clone)]
pub struct SimulationResult {
    pub facility_kw: [f32; STEPS_96],
    pub zone_temperatures_f: [[f32; 6]; STEPS_96],
    pub daily_kwh: f64,
    pub peak_kw: f64,
    pub peak_timestep: usize,
    pub energy_cost: f64,
    pub incremental_demand_kw: f64,
    pub incremental_demand_cost: f64,
    pub new_billing_peak_kw: f64,
    pub comfort_violations: i64,
    pub ood: bool,
    pub ood_status: Option<String>,
    pub recommend: bool,
    pub honesty: String,
    pub provenance: String,
    pub strategy_id: String,
    pub unsupported_reason: Option<String>,
    pub outcome_flags: Vec<String>,
}

/// One-day incremental demand accounting (never charge full monthly demand alone).
pub fn incremental_demand(
    existing_billing_peak_kw: f64,
    simulated_day_peak_kw: f64,
    demand_rate_per_kw: f64,
) -> (f64, f64, f64) {
    let new_peak = billing_period_demand_kw(existing_billing_peak_kw, simulated_day_peak_kw);
    let incremental_kw = (new_peak - existing_billing_peak_kw).max(0.0);
    let incremental_cost = incremental_kw * demand_rate_per_kw;
    (new_peak, incremental_kw, incremental_cost)
}

/// Fill facility/zone arrays from a 96-step hybrid walk summary series.
pub fn result_from_series(
    facility_kw: &[f64],
    zones: &[[f64; 6]],
    strategy_id: &str,
    existing_billing_peak_kw: f64,
    demand_rate_per_kw: f64,
    energy_cost: f64,
    comfort_violations: i64,
    ood: bool,
    ood_status: Option<String>,
    recommend: bool,
    honesty: &str,
    provenance: &str,
    outcome_flags: Vec<String>,
    unsupported_reason: Option<String>,
) -> SimulationResult {
    let mut fac = [0.0_f32; STEPS_96];
    let mut zt = [[0.0_f32; 6]; STEPS_96];
    let n = facility_kw.len().min(STEPS_96);
    for i in 0..n {
        fac[i] = facility_kw[i] as f32;
        if let Some(row) = zones.get(i) {
            zt[i] = [
                row[0] as f32,
                row[1] as f32,
                row[2] as f32,
                row[3] as f32,
                row[4] as f32,
                row[5] as f32,
            ];
        }
    }
    let peak_kw = facility_kw
        .iter()
        .copied()
        .fold(f64::NEG_INFINITY, f64::max);
    let peak_timestep = facility_kw
        .iter()
        .enumerate()
        .max_by(|(_, a), (_, b)| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal))
        .map(|(i, _)| i)
        .unwrap_or(0);
    let daily_kwh = facility_kw.iter().sum::<f64>() * 0.25;
    let (new_billing_peak_kw, incremental_demand_kw, incremental_demand_cost) =
        incremental_demand(existing_billing_peak_kw, peak_kw, demand_rate_per_kw);
    SimulationResult {
        facility_kw: fac,
        zone_temperatures_f: zt,
        daily_kwh,
        peak_kw,
        peak_timestep,
        energy_cost,
        incremental_demand_kw,
        incremental_demand_cost,
        new_billing_peak_kw,
        comfort_violations,
        ood,
        ood_status,
        recommend,
        honesty: honesty.into(),
        provenance: provenance.into(),
        strategy_id: strategy_id.into(),
        unsupported_reason,
        outcome_flags,
    }
}

/// Row from STRATEGY ENUMERATION (not mathematical optimization).
#[derive(Debug, Clone)]
pub struct StrategyEnumRow {
    pub strategy_id: String,
    pub peak_kw: f64,
    pub daily_kwh: f64,
    pub energy_cost: f64,
    pub incremental_demand_kw: f64,
    pub incremental_demand_cost: f64,
    pub total_incremental_cost: f64,
    pub comfort_violations: i64,
    pub ood: bool,
    pub feasible: bool,
    pub reject_reason: Option<String>,
}

/// Future Annual Replay interface (not implemented — HEURISTIC annual remains).
#[derive(Debug, Clone, Default)]
pub struct AnnualReplayPlan {
    pub note: String,
}

impl AnnualReplayPlan {
    pub fn stub() -> Self {
        Self {
            note: ("FUTURE Annual Replay: 365 weather/init days, chronological sim, \
                 monthly peak-to-date, verified tariff/ratchet, baseline vs DSM bills. \
                 Current annual rollup is HEURISTIC only.")
                .into(),
        }
    }
}

/// Documented future objective (do not implement optimizer here).
pub fn future_objective_doc() -> &'static str {
    "total_cost = sum(interval_kw * 0.25 * energy_rate) \
     + incremental_monthly_demand_cost + comfort_penalty + equipment_cycling_penalty; \
     comfort limits are hard feasibility constraints."
}

pub fn zone_col_names() -> [&'static str; 6] {
    ZONE_TEMP_COLS
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn incremental_demand_zero_when_below_existing() {
        let (new_p, inc_kw, inc_cost) = incremental_demand(100.0, 80.0, 12.0);
        assert!((new_p - 100.0).abs() < 1e-9);
        assert!(inc_kw.abs() < 1e-9);
        assert!(inc_cost.abs() < 1e-9);
    }

    #[test]
    fn incremental_demand_charges_only_delta() {
        let (new_p, inc_kw, inc_cost) = incremental_demand(100.0, 120.0, 12.0);
        assert!((new_p - 120.0).abs() < 1e-9);
        assert!((inc_kw - 20.0).abs() < 1e-9);
        assert!((inc_cost - 240.0).abs() < 1e-9);
    }

    #[test]
    fn named_strategy_compiles_to_control_schedule_96() {
        let sched = load_control_schedule("stagger_preheat").expect("fixture");
        assert_eq!(sched.steps.len(), STEPS_96);
        let _: ControlSchedule96 = sched;
    }
}
