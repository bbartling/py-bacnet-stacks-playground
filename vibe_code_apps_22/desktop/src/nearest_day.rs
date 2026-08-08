//! Nearest-Day + EnergyPlus Delta engineering benchmark (not ML).
//!
//! Loads compact `nearest_day_eplus_delta_v1.json` and computes neighbors live
//! from midnight / OAT96 / strategy inputs.

use std::fs;
use std::path::{Path, PathBuf};

use anyhow::{bail, Context, Result};
use serde::Deserialize;

use crate::features_15min::{STEPS_96, ZONE_TEMP_COLS};
use crate::hybrid::{HybridStep, HybridSummary, HybridWalk};

const LIBRARY_NAME: &str = "nearest_day_eplus_delta_v1.json";

#[derive(Debug, Clone, Deserialize)]
pub struct NearestDayLibrary {
    pub schema: String,
    pub honesty: Option<String>,
    pub k: Option<usize>,
    pub ood_threshold: f64,
    #[serde(default)]
    pub distance_weights: DistanceWeights,
    #[serde(default)]
    pub scale_means: std::collections::BTreeMap<String, f64>,
    #[serde(default)]
    pub scale_stds: std::collections::BTreeMap<String, f64>,
    #[serde(default)]
    pub oat_mean_traj: Vec<f64>,
    #[serde(default)]
    pub days: Vec<LibDay>,
    #[serde(default)]
    pub eplus_delta_records: Vec<EplusDeltaRec>,
    pub watermark: Option<String>,
    pub eplus_watermark: Option<String>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct DistanceWeights {
    #[serde(default = "w2")]
    pub weekend_mismatch: f64,
    #[serde(default = "w1")]
    pub oat_traj: f64,
    #[serde(default = "w075")]
    pub midnight_oat: f64,
    #[serde(default = "w075")]
    pub midnight_kw: f64,
    #[serde(default = "w1")]
    pub midnight_zones: f64,
}

impl Default for DistanceWeights {
    fn default() -> Self {
        Self {
            weekend_mismatch: 2.0,
            oat_traj: 1.0,
            midnight_oat: 0.75,
            midnight_kw: 0.75,
            midnight_zones: 1.0,
        }
    }
}

fn w2() -> f64 {
    2.0
}
fn w1() -> f64 {
    1.0
}
fn w075() -> f64 {
    0.75
}

#[derive(Debug, Clone, Deserialize)]
pub struct LibDay {
    pub day: String,
    pub is_weekend: f64,
    pub midnight_oat: f64,
    pub midnight_kw: f64,
    pub midnight_zones: Vec<f64>,
    pub oat_96: Vec<f64>,
    pub y_96x7: Vec<Vec<f64>>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct EplusDeltaRec {
    pub pair_id: String,
    pub strategy_id: String,
    pub oat_96: Vec<f64>,
    pub init_zones: Vec<f64>,
    pub delta_96x7: Vec<Vec<f64>>,
}

#[derive(Debug, Clone)]
pub struct NeighborHit {
    pub day: String,
    pub total_distance: f64,
    pub oat_distance: f64,
    pub midnight_kw_distance: f64,
    pub midnight_zone_distance: f64,
    pub weekend_match: bool,
}

#[derive(Debug, Clone)]
pub struct NearestDayResult {
    pub walk: HybridWalk,
    pub neighbors: Vec<NeighborHit>,
    pub ood: bool,
    pub ood_status: Option<String>,
    pub nearest_distance: Option<f64>,
    pub ood_threshold: f64,
    pub failed_criteria: Vec<String>,
    pub recommend: bool,
    pub outcome_flags: Vec<String>,
    pub watermark: Option<String>,
    pub baseline_peak_kw: f64,
    pub hybrid_peak_kw: f64,
    pub baseline_kwh: f64,
    pub hybrid_kwh: f64,
}

pub struct NearestDayEngine {
    pub library: NearestDayLibrary,
    pub path: PathBuf,
}

fn candidate_library_paths() -> Vec<PathBuf> {
    let mut out = Vec::new();
    if let Some(dir) = std::env::var_os("LAKESIDE_ONNX_DIR") {
        out.push(PathBuf::from(dir).join(LIBRARY_NAME));
    }
    if let Ok(exe) = std::env::current_exe() {
        if let Some(d) = exe.parent() {
            out.push(d.join(LIBRARY_NAME));
            out.push(d.join("artifacts").join(LIBRARY_NAME));
        }
    }
    if let Some(manifest) = option_env!("CARGO_MANIFEST_DIR") {
        let m = Path::new(manifest);
        out.push(m.join("artifacts").join(LIBRARY_NAME));
        out.push(m.join("..").join("ml").join("artifacts").join(LIBRARY_NAME));
        out.push(
            m.join("..")
                .join("ml")
                .join("artifacts")
                .join("fixtures")
                .join(LIBRARY_NAME),
        );
    }
    out
}

impl NearestDayEngine {
    pub fn load_default() -> Result<Self> {
        for p in candidate_library_paths() {
            if p.is_file() {
                return Self::load(&p);
            }
        }
        bail!("nearest-day library not found ({LIBRARY_NAME})")
    }

    pub fn load(path: &Path) -> Result<Self> {
        let txt = fs::read_to_string(path).with_context(|| format!("read {}", path.display()))?;
        let library: NearestDayLibrary =
            serde_json::from_str(&txt).context("parse nearest_day library")?;
        Ok(Self {
            library,
            path: path.to_path_buf(),
        })
    }

    fn z(&self, key: &str, value: f64) -> f64 {
        let mu = *self.library.scale_means.get(key).unwrap_or(&0.0);
        let mut sd = *self.library.scale_stds.get(key).unwrap_or(&1.0);
        if sd.abs() < 1e-9 {
            sd = 1.0;
        }
        (value - mu) / sd
    }

    fn distance(
        &self,
        q_weekend: f64,
        q_oat: &[f64],
        q_mo: f64,
        q_kw: f64,
        q_zones: &[f64],
        d: &LibDay,
    ) -> NeighborHit {
        let weekend_mismatch = if (q_weekend - d.is_weekend).abs() < 0.5 {
            0.0
        } else {
            1.0
        };
        let mut oat_l2 = 0.0;
        let n = q_oat.len().min(d.oat_96.len()).min(STEPS_96);
        for i in 0..n {
            let e = q_oat[i] - d.oat_96[i];
            oat_l2 += e * e;
        }
        let oat_l2 = oat_l2.sqrt();
        let oat_sd = self
            .library
            .scale_stds
            .get("oat_traj_l2")
            .copied()
            .unwrap_or(1.0)
            .max(1e-9);
        let oat_z = oat_l2 / oat_sd;
        let mid_oat = (self.z("midnight_oat", q_mo) - self.z("midnight_oat", d.midnight_oat)).abs();
        let mid_kw = (self.z("midnight_kw", q_kw) - self.z("midnight_kw", d.midnight_kw)).abs();
        let mut zone = 0.0;
        for zi in 0..6 {
            let qv = q_zones.get(zi).copied().unwrap_or(68.0);
            let dv = d.midnight_zones.get(zi).copied().unwrap_or(68.0);
            zone += (self.z(&format!("zone_{zi}"), qv) - self.z(&format!("zone_{zi}"), dv)).abs();
        }
        zone /= 6.0;
        let w = &self.library.distance_weights;
        let total = w.weekend_mismatch * weekend_mismatch
            + w.oat_traj * oat_z
            + w.midnight_oat * mid_oat
            + w.midnight_kw * mid_kw
            + w.midnight_zones * zone;
        NeighborHit {
            day: d.day.clone(),
            total_distance: total,
            oat_distance: oat_z,
            midnight_kw_distance: mid_kw,
            midnight_zone_distance: zone,
            weekend_match: weekend_mismatch < 0.5,
        }
    }

    pub fn rollout(
        &self,
        midnight_kw: f32,
        midnight_zones: [f32; 6],
        oat_96: &[f32],
        is_weekend: bool,
        strategy_id: &str,
        before_day: Option<&str>,
        existing_billing_peak_kw: f32,
    ) -> Result<NearestDayResult> {
        if oat_96.len() != STEPS_96 {
            bail!("oat_96 len {} != {STEPS_96}", oat_96.len());
        }
        let q_weekend = if is_weekend { 1.0 } else { 0.0 };
        let q_oat: Vec<f64> = oat_96.iter().map(|v| *v as f64).collect();
        let q_zones: Vec<f64> = midnight_zones.iter().map(|v| *v as f64).collect();
        let q_mo = q_oat[0];
        let q_kw = midnight_kw as f64;
        let before = before_day.unwrap_or("9999-12-31");

        let mut hits: Vec<NeighborHit> = self
            .library
            .days
            .iter()
            .filter(|d| d.day.as_str() < before)
            .map(|d| self.distance(q_weekend, &q_oat, q_mo, q_kw, &q_zones, d))
            .collect();
        hits.sort_by(|a, b| {
            a.total_distance
                .partial_cmp(&b.total_distance)
                .unwrap_or(std::cmp::Ordering::Equal)
                .then_with(|| a.day.cmp(&b.day))
        });
        let k = self.library.k.unwrap_or(10).max(1);
        hits.truncate(k);

        let mut failed = Vec::new();
        let nearest = hits.first().map(|h| h.total_distance);
        let mut ood = false;
        if hits.is_empty() {
            ood = true;
            failed.push("no_eligible_historical_neighbors".into());
        }
        if let Some(nd) = nearest {
            if nd > self.library.ood_threshold {
                ood = true;
                failed.push(format!(
                    "nearest_distance={nd} exceeds threshold={}",
                    self.library.ood_threshold
                ));
            }
        }

        // Pointwise median / p10 / p90
        let mut baseline = vec![vec![0.0_f64; 7]; STEPS_96];
        let mut p10 = baseline.clone();
        let mut p90 = baseline.clone();
        if !hits.is_empty() {
            let by: std::collections::BTreeMap<_, _> = self
                .library
                .days
                .iter()
                .map(|d| (d.day.as_str(), d))
                .collect();
            for t in 0..STEPS_96 {
                for c in 0..7 {
                    let mut vals: Vec<f64> = hits
                        .iter()
                        .filter_map(|h| by.get(h.day.as_str()))
                        .filter_map(|d| d.y_96x7.get(t).and_then(|row| row.get(c)).copied())
                        .collect();
                    vals.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
                    if vals.is_empty() {
                        continue;
                    }
                    baseline[t][c] = percentile_sorted(&vals, 50.0);
                    p10[t][c] = percentile_sorted(&vals, 10.0);
                    p90[t][c] = percentile_sorted(&vals, 90.0);
                }
            }
        }

        // E+ delta match
        let mut delta = vec![vec![0.0_f64; 7]; STEPS_96];
        let pool: Vec<_> = self
            .library
            .eplus_delta_records
            .iter()
            .filter(|r| r.strategy_id == strategy_id)
            .collect();
        if pool.is_empty() {
            ood = true;
            // Named strategies without a compatible E+ delta are unsupported —
            // never interpolate arbitrary ControlSchedule96 without a validated method.
            failed.push(crate::simulation::UNSUPPORTED_CONTROL_SCHEDULE.into());
            failed.push(format!("no_eplus_records_for_strategy={strategy_id}"));
        } else {
            let mut best_d = f64::INFINITY;
            let mut best: Option<&EplusDeltaRec> = None;
            for r in &pool {
                let mut oat_d = 0.0;
                for i in 0..STEPS_96.min(r.oat_96.len()) {
                    let e = q_oat[i] - r.oat_96[i];
                    oat_d += e * e;
                }
                let mut z_d = 0.0;
                for i in 0..6.min(r.init_zones.len()) {
                    let e = q_zones[i] - r.init_zones[i];
                    z_d += e * e;
                }
                let dist = oat_d.sqrt() + z_d.sqrt();
                if dist < best_d {
                    best_d = dist;
                    best = Some(r);
                }
            }
            if let Some(r) = best {
                for t in 0..STEPS_96.min(r.delta_96x7.len()) {
                    for c in 0..7.min(r.delta_96x7[t].len()) {
                        delta[t][c] = r.delta_96x7[t][c];
                    }
                }
            }
        }

        let mut hybrid = baseline.clone();
        for t in 0..STEPS_96 {
            for c in 0..7 {
                hybrid[t][c] = baseline[t][c] + delta[t][c];
            }
        }

        let base_kw: Vec<f64> = baseline.iter().map(|r| r[0]).collect();
        let hyb_kw: Vec<f64> = hybrid.iter().map(|r| r[0]).collect();
        let peak_b = max_f64(&base_kw);
        let peak_h = max_f64(&hyb_kw);
        let kwh_b = base_kw.iter().sum::<f64>() * 0.25;
        let kwh_h = hyb_kw.iter().sum::<f64>() * 0.25;
        let mut flags = Vec::new();
        let mut recommend = !ood;
        if peak_h - peak_b > 0.0 {
            flags.push("DSM_WORSENS_PEAK".into());
            recommend = false;
        }
        if kwh_h - kwh_b > 0.0 {
            flags.push("DSM_WORSENS_ENERGY".into());
            recommend = false;
        }
        if ood {
            recommend = false;
        }
        let _billing = billing_period_demand_kw(existing_billing_peak_kw as f64, peak_h);

        let mut steps = Vec::with_capacity(STEPS_96);
        let htg_sp = 68.0_f64;
        let band = 2.0_f64;
        let mut comfort_cum = 0_i64;
        for t in 0..STEPS_96 {
            let mut bz = std::collections::BTreeMap::new();
            let mut hz = std::collections::BTreeMap::new();
            let mut dz = std::collections::BTreeMap::new();
            for (zi, name) in ZONE_TEMP_COLS.iter().enumerate() {
                let zt = hybrid[t][zi + 1];
                if zt < htg_sp - band {
                    comfort_cum += 1;
                }
                bz.insert((*name).to_string(), baseline[t][zi + 1]);
                hz.insert((*name).to_string(), zt);
                dz.insert((*name).to_string(), delta[t][zi + 1]);
            }
            steps.push(HybridStep {
                step_15: t as i64,
                baseline_facility_kw: baseline[t][0],
                hybrid_facility_kw: hybrid[t][0],
                delta_facility_kw: delta[t][0],
                cumulative_kwh_baseline: base_kw[..=t].iter().sum::<f64>() * 0.25,
                cumulative_kwh_hybrid: hyb_kw[..=t].iter().sum::<f64>() * 0.25,
                comfort_violations_cum: comfort_cum,
                baseline_zone_temps_f: bz,
                delta_zone_temps_f: dz,
                hybrid_zone_temps_f: hz,
            });
        }

        let peak_step_b = base_kw
            .iter()
            .enumerate()
            .max_by(|(_, a), (_, b)| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal))
            .map(|(i, _)| i as i64)
            .unwrap_or(0);
        let peak_step_h = hyb_kw
            .iter()
            .enumerate()
            .max_by(|(_, a), (_, b)| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal))
            .map(|(i, _)| i as i64)
            .unwrap_or(0);

        let walk = HybridWalk {
            contract_version: "nearest_day_eplus_delta_v1".into(),
            honesty: self
                .library
                .honesty
                .clone()
                .unwrap_or_else(|| "SIMPLE_HYBRID_SCREENING".into()),
            steps,
            summary: HybridSummary {
                cumulative_kwh_baseline: kwh_b,
                cumulative_kwh_hybrid: kwh_h,
                peak_kw_baseline: peak_b,
                peak_kw_hybrid: peak_h,
                peak_step_baseline: peak_step_b,
                peak_step_hybrid: peak_step_h,
                comfort_violations: comfort_cum,
                delta_peak_kw: peak_h - peak_b,
                delta_kwh: kwh_h - kwh_b,
            },
            champion_baseline: Some("nearest_day_median".into()),
            champion_delta: Some(format!("eplus:{strategy_id}")),
            outcome_flag: flags.first().cloned(),
            source: Some("nearest_day_engine".into()),
            weather_mode: None,
            comfort_htg_sp_f: Some(htg_sp),
            comfort_band_f: Some(band),
            ship_watermark: self
                .library
                .watermark
                .clone()
                .or(self.library.eplus_watermark.clone()),
        };

        Ok(NearestDayResult {
            walk,
            neighbors: hits,
            ood,
            ood_status: if ood {
                Some("OUT_OF_DISTRIBUTION".into())
            } else {
                None
            },
            nearest_distance: nearest,
            ood_threshold: self.library.ood_threshold,
            failed_criteria: failed,
            recommend,
            outcome_flags: flags,
            watermark: self
                .library
                .watermark
                .clone()
                .or(self.library.eplus_watermark.clone()),
            baseline_peak_kw: peak_b,
            hybrid_peak_kw: peak_h,
            baseline_kwh: kwh_b,
            hybrid_kwh: kwh_h,
        })
    }
}

pub fn billing_period_demand_kw(existing_period_peak_kw: f64, simulated_day_peak_kw: f64) -> f64 {
    existing_period_peak_kw.max(simulated_day_peak_kw)
}

fn max_f64(xs: &[f64]) -> f64 {
    xs.iter().copied().fold(f64::NEG_INFINITY, f64::max)
}

fn percentile_sorted(sorted: &[f64], q: f64) -> f64 {
    if sorted.is_empty() {
        return 0.0;
    }
    if sorted.len() == 1 {
        return sorted[0];
    }
    let pos = (q / 100.0) * (sorted.len() as f64 - 1.0);
    let lo = pos.floor() as usize;
    let hi = pos.ceil() as usize;
    if lo == hi {
        sorted[lo]
    } else {
        let w = pos - lo as f64;
        sorted[lo] * (1.0 - w) + sorted[hi] * w
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn billing_demand_uses_max() {
        assert!((billing_period_demand_kw(100.0, 80.0) - 100.0).abs() < 1e-9);
        assert!((billing_period_demand_kw(100.0, 120.0) - 120.0).abs() < 1e-9);
    }

    #[test]
    fn percentile_basic() {
        let v = vec![1.0, 2.0, 3.0, 4.0, 5.0];
        assert!((percentile_sorted(&v, 50.0) - 3.0).abs() < 1e-9);
    }
}
