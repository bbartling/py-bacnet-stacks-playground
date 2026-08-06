//! Live hybrid 96-step ONNX engine (real baseline + E+ delta).
//!
//! Fail-closed without both 15-min ONNX stems. Quarantines hourly ship path.

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use anyhow::{anyhow, bail, Context, Result};
use ort::session::builder::GraphOptimizationLevel;
use ort::session::Session;
use ort::value::Tensor;
use serde::Deserialize;

use crate::features::{default_occ_frac, StrategyKnobs};
use crate::features_15min::{
    RowMap, FEATURE_COLS_15MIN_MT, HP_ON_COLS, N_FEATURES_15MIN_MT, N_OUTPUTS, OCC_FRAC_COLS,
    STEPS_96, STRATEGY_IDS_15, ZONE_TEMP_COLS,
};
use crate::hybrid::{HybridStep, HybridSummary, HybridWalk};

const HONESTY: &str = "HYBRID_SCREENING";
const CONTRACT_VERSION: &str = "hybrid_dsm_96_v1";

#[derive(Debug, Deserialize)]
pub struct HybridFeatureMeta {
    pub feature_cols: Vec<String>,
    #[serde(default)]
    pub target_cols: Vec<String>,
    #[serde(default)]
    pub n_features: Option<usize>,
    #[serde(default)]
    pub n_outputs: Option<usize>,
    #[serde(default)]
    pub scaler: Option<String>,
    #[serde(default)]
    pub honesty: Option<String>,
    #[serde(default)]
    pub champion: Option<String>,
}

pub struct MultiOutOnnx {
    session: Session,
    pub feature_cols: Vec<String>,
    pub meta: HybridFeatureMeta,
}

fn ort_err(e: impl std::fmt::Display) -> anyhow::Error {
    anyhow!("{e}")
}

impl MultiOutOnnx {
    pub fn load(onnx_path: &Path, meta_path: &Path) -> Result<Self> {
        let meta_txt = std::fs::read_to_string(meta_path)
            .with_context(|| format!("read {}", meta_path.display()))?;
        let meta: HybridFeatureMeta =
            serde_json::from_str(&meta_txt).context("parse hybrid feature_meta")?;
        let n_feat = meta.n_features.unwrap_or(meta.feature_cols.len());
        if n_feat != meta.feature_cols.len() {
            bail!(
                "n_features {} != feature_cols {}",
                n_feat,
                meta.feature_cols.len()
            );
        }
        if meta.feature_cols.len() != N_FEATURES_15MIN_MT {
            bail!(
                "expected {} features, got {} ({})",
                N_FEATURES_15MIN_MT,
                meta.feature_cols.len(),
                meta_path.display()
            );
        }
        let session = Session::builder()
            .map_err(ort_err)?
            .with_optimization_level(GraphOptimizationLevel::Level3)
            .map_err(ort_err)?
            .commit_from_file(onnx_path)
            .map_err(ort_err)
            .with_context(|| format!("load ONNX {}", onnx_path.display()))?;
        Ok(Self {
            session,
            feature_cols: meta.feature_cols.clone(),
            meta,
        })
    }

    pub fn predict7(&mut self, features: &[f32]) -> Result<[f32; N_OUTPUTS]> {
        if features.len() != self.feature_cols.len() {
            bail!(
                "feature len {} != {}",
                features.len(),
                self.feature_cols.len()
            );
        }
        let input =
            Tensor::from_array(([1usize, features.len()], features.to_vec())).map_err(ort_err)?;
        let outputs = self
            .session
            .run(ort::inputs!["features" => input])
            .map_err(ort_err)?;
        let (_shape, data) = outputs["outputs"]
            .try_extract_tensor::<f32>()
            .map_err(ort_err)?;
        if data.len() < N_OUTPUTS {
            bail!("expected {} outputs, got {}", N_OUTPUTS, data.len());
        }
        let mut out = [0.0_f32; N_OUTPUTS];
        out.copy_from_slice(&data[..N_OUTPUTS]);
        Ok(out)
    }
}

pub struct HybridEngine {
    pub baseline: MultiOutOnnx,
    pub delta: MultiOutOnnx,
    pub baseline_path: PathBuf,
    pub delta_path: PathBuf,
}

impl HybridEngine {
    pub fn load_default() -> Result<Self> {
        let (base_onnx, base_meta, delta_onnx, delta_meta) = default_hybrid_artifact_paths();
        if !base_onnx.is_file() || !delta_onnx.is_file() {
            bail!(
                "hybrid ONNX missing — need real_baseline_15min_v1.onnx + eplus_delta_15min_v1.onnx. Tried base={} delta={}",
                base_onnx.display(),
                delta_onnx.display()
            );
        }
        let baseline = MultiOutOnnx::load(&base_onnx, &base_meta)?;
        let delta = MultiOutOnnx::load(&delta_onnx, &delta_meta)?;
        if baseline.feature_cols != delta.feature_cols {
            bail!("baseline/delta feature_cols mismatch");
        }
        Ok(Self {
            baseline,
            delta,
            baseline_path: base_onnx,
            delta_path: delta_onnx,
        })
    }

    pub fn rollout(
        &mut self,
        init_kw: f32,
        init_zones: [f32; 6],
        oat_96: &[f32; STEPS_96],
        rh_96: &[f32; STEPS_96],
        ghi_96: &[f32; STEPS_96],
        month: f32,
        doy: f32,
        is_weekend: f32,
        strategy_id: &str,
        force_247_dsm: bool,
    ) -> Result<HybridWalk> {
        if !init_kw.is_finite() || init_kw <= 0.0 {
            bail!("init facility_kw must be finite measured midnight (>0)");
        }
        for (i, z) in init_zones.iter().enumerate() {
            if !z.is_finite() {
                bail!("init zone temp[{i}] not finite");
            }
        }

        let knobs_base = StrategyKnobs::for_id("baseline");
        let knobs_dsm = if force_247_dsm {
            StrategyKnobs::for_id("flat_24_7")
        } else {
            StrategyKnobs::for_id(strategy_id)
        };
        let sid_dsm = if force_247_dsm {
            "flat_24_7"
        } else {
            strategy_id
        };

        let mut state_b = BTreeMap::new();
        state_b.insert("facility_kw_lag1".into(), init_kw);
        state_b.insert("facility_kw_lag2".into(), init_kw);
        state_b.insert("oat_lag1".into(), oat_96[0]);
        for (i, c) in ZONE_TEMP_COLS.iter().enumerate() {
            state_b.insert(format!("{c}_lag1"), init_zones[i]);
        }

        let mut state_d = BTreeMap::new();
        state_d.insert("facility_kw_lag1".into(), 0.0);
        state_d.insert("facility_kw_lag2".into(), 0.0);
        state_d.insert("oat_lag1".into(), oat_96[0]);
        for c in ZONE_TEMP_COLS {
            state_d.insert(format!("{c}_lag1"), 0.0);
        }

        let mut steps = Vec::with_capacity(STEPS_96);
        let mut cum_b = 0.0_f64;
        let mut cum_h = 0.0_f64;
        let mut peak_b = f64::NEG_INFINITY;
        let mut peak_h = f64::NEG_INFINITY;
        let mut peak_b_t = 0_i64;
        let mut peak_h_t = 0_i64;
        let mut viol = 0_i64;
        let comfort_sp = 68.0_f64;
        let comfort_band = 2.0_f64;
        let mut hdd_acc = 0.0_f32;
        let cols = self.baseline.feature_cols.clone();

        for step in 0..STEPS_96 {
            let oat = oat_96[step];
            let rh = rh_96[step];
            let ghi = ghi_96[step];
            let hdd = (65.0 - oat).max(0.0);
            if step < 28 {
                hdd_acc += hdd;
            }
            let hour = step as f32 / 4.0;
            let occupied = if (28..64).contains(&step) { 1.0 } else { 0.0 };

            let mut row_b = RowMap::default();
            let mut row_d = RowMap::default();
            for row in [&mut row_b, &mut row_d] {
                row.set("step_15", step as f32);
                row.set(
                    "sin_step",
                    (2.0 * std::f32::consts::PI * step as f32 / 96.0).sin(),
                );
                row.set(
                    "cos_step",
                    (2.0 * std::f32::consts::PI * step as f32 / 96.0).cos(),
                );
                row.set("hour_ending", hour);
                row.set("month", month);
                row.set("doy", doy);
                row.set("is_weekend", is_weekend);
                row.set("occupied", occupied);
                row.set("oat_f", oat);
                row.set("rh_pct", rh);
                row.set("ghi", ghi);
                row.set("hdd65", hdd);
                row.set("hdd65_cum_night", hdd_acc);
                row.set("hours_to_occupy", ((28 - step as i32).max(0) as f32) / 4.0);
            }

            // controls
            let he = (step / 4).min(23);
            let weekend = is_weekend > 0.5;
            fill_controls(&mut row_b, "baseline", &knobs_base, he, weekend, false);
            fill_controls(&mut row_d, sid_dsm, &knobs_dsm, he, weekend, force_247_dsm);

            row_b.set("oat_lag1", *state_b.get("oat_lag1").unwrap_or(&oat));
            row_d.set("oat_lag1", *state_d.get("oat_lag1").unwrap_or(&oat));
            for (k, v) in &state_b {
                row_b.set(k, *v);
            }
            for (k, v) in &state_d {
                row_d.set(k, *v);
            }

            let xb = row_b.to_feature_vec(&cols);
            let xd = row_d.to_feature_vec(&cols);
            let base_y = self.baseline.predict7(&xb)?;
            let delta_y = self.delta.predict7(&xd)?;
            let mut hybrid_y = [0.0_f32; N_OUTPUTS];
            for i in 0..N_OUTPUTS {
                hybrid_y[i] = base_y[i] + delta_y[i];
            }

            let kw_b = base_y[0] as f64;
            let kw_h = hybrid_y[0] as f64;
            cum_b += kw_b * 0.25;
            cum_h += kw_h * 0.25;
            if kw_b > peak_b {
                peak_b = kw_b;
                peak_b_t = step as i64;
            }
            if kw_h > peak_h {
                peak_h = kw_h;
                peak_h_t = step as i64;
            }
            for i in 0..6 {
                let t = hybrid_y[1 + i] as f64;
                if t < comfort_sp - comfort_band {
                    viol += 1;
                }
            }

            steps.push(HybridStep {
                step_15: step as i64,
                baseline_facility_kw: kw_b,
                hybrid_facility_kw: kw_h,
                delta_facility_kw: delta_y[0] as f64,
                cumulative_kwh_baseline: cum_b,
                cumulative_kwh_hybrid: cum_h,
                comfort_violations_cum: viol,
            });

            // lag updates
            let lag1_b = *state_b.get("facility_kw_lag1").unwrap_or(&init_kw);
            state_b.insert("facility_kw_lag2".into(), lag1_b);
            state_b.insert("facility_kw_lag1".into(), base_y[0]);
            state_b.insert("oat_lag1".into(), oat);
            for i in 0..6 {
                state_b.insert(format!("{}_lag1", ZONE_TEMP_COLS[i]), base_y[1 + i]);
            }

            let lag1_d = *state_d.get("facility_kw_lag1").unwrap_or(&0.0);
            state_d.insert("facility_kw_lag2".into(), lag1_d);
            state_d.insert("facility_kw_lag1".into(), delta_y[0]);
            state_d.insert("oat_lag1".into(), oat);
            for i in 0..6 {
                state_d.insert(format!("{}_lag1", ZONE_TEMP_COLS[i]), delta_y[1 + i]);
            }
        }

        let delta_peak = peak_h - peak_b;
        let outcome = if delta_peak > 0.0 {
            Some("DSM_WORSENS_PEAK".into())
        } else {
            None
        };

        Ok(HybridWalk {
            contract_version: CONTRACT_VERSION.into(),
            honesty: HONESTY.into(),
            steps,
            summary: HybridSummary {
                cumulative_kwh_baseline: cum_b,
                cumulative_kwh_hybrid: cum_h,
                peak_kw_baseline: peak_b,
                peak_kw_hybrid: peak_h,
                peak_step_baseline: peak_b_t,
                peak_step_hybrid: peak_h_t,
                comfort_violations: viol,
                delta_peak_kw: delta_peak,
                delta_kwh: cum_h - cum_b,
            },
            champion_baseline: self.baseline.meta.champion.clone(),
            champion_delta: self.delta.meta.champion.clone(),
            outcome_flag: outcome,
            source: Some("live_onnx".into()),
        })
    }
}

fn fill_controls(
    row: &mut RowMap,
    strategy_id: &str,
    knobs: &StrategyKnobs,
    he: usize,
    weekend: bool,
    force_247: bool,
) {
    let (occ, hp) = if force_247 || strategy_id == "flat_24_7" {
        ([1.0_f32; 6], [1.0_f32; 6])
    } else {
        let o = default_occ_frac(he, strategy_id, weekend);
        let mut hp = [0.0_f32; 6];
        for z in 0..6 {
            hp[z] = if o[z] > 0.05 { 1.0 } else { 0.0 };
        }
        // morning stagger: delay HP for some zones during HE 05–07
        if strategy_id == "stagger_preheat" && (5..7).contains(&he) {
            for z in 0..6 {
                if z > (he - 5) {
                    hp[z] = 0.0;
                }
            }
        }
        (o, hp)
    };
    let mut sum_occ = 0.0;
    let mut sum_hp = 0.0;
    for z in 0..6 {
        row.set(OCC_FRAC_COLS[z], occ[z]);
        row.set(HP_ON_COLS[z], hp[z]);
        sum_occ += occ[z];
        sum_hp += hp[z];
    }
    row.set("sum_occ_frac", sum_occ);
    row.set("sum_hp_on", sum_hp);
    row.set("preheat_lead_h", knobs.preheat_lead_h);
    row.set("stagger_min", knobs.stagger_min);
    row.set("unocc_htg_sp_f", knobs.unocc_htg_sp_f);
    row.set("occ_htg_sp_f", knobs.occ_htg_sp_f);
    for s in STRATEGY_IDS_15 {
        row.set(
            &format!("strategy_{s}"),
            if s == strategy_id { 1.0 } else { 0.0 },
        );
    }
}

pub fn default_hybrid_artifact_paths() -> (PathBuf, PathBuf, PathBuf, PathBuf) {
    let candidates = [
        std::env::var_os("LAKESIDE_ONNX_DIR").map(PathBuf::from),
        std::env::current_exe()
            .ok()
            .and_then(|p| p.parent().map(|d| d.to_path_buf())),
        option_env!("CARGO_MANIFEST_DIR").map(|s| Path::new(s).join("artifacts")),
        option_env!("CARGO_MANIFEST_DIR").map(|s| Path::new(s).join("..").join("ml").join("artifacts")),
        Some(Path::new("ml").join("artifacts")),
        Some(Path::new("..").join("ml").join("artifacts")),
    ];
    for base in candidates.into_iter().flatten() {
        let bo = base.join("real_baseline_15min_v1.onnx");
        let bm = base.join("real_baseline_15min_v1_feature_meta.json");
        let do_ = base.join("eplus_delta_15min_v1.onnx");
        let dm = base.join("eplus_delta_15min_v1_feature_meta.json");
        if bo.is_file() && bm.is_file() && do_.is_file() && dm.is_file() {
            return (bo, bm, do_, dm);
        }
    }
    let fallback = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("ml")
        .join("artifacts");
    (
        fallback.join("real_baseline_15min_v1.onnx"),
        fallback.join("real_baseline_15min_v1_feature_meta.json"),
        fallback.join("eplus_delta_15min_v1.onnx"),
        fallback.join("eplus_delta_15min_v1_feature_meta.json"),
    )
}

/// Expand 24 hourly OAT values to 96 quarter-hour steps (piecewise constant).
pub fn expand_oat_24_to_96(oat24: &[f32; 24]) -> [f32; STEPS_96] {
    let mut out = [0.0_f32; STEPS_96];
    for step in 0..STEPS_96 {
        out[step] = oat24[(step / 4).min(23)];
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn expand_oat_length() {
        let oat = [20.0_f32; 24];
        let e = expand_oat_24_to_96(&oat);
        assert_eq!(e.len(), 96);
        assert!((e[0] - 20.0).abs() < 1e-6);
    }

    #[test]
    fn feature_cols_static_match() {
        assert_eq!(FEATURE_COLS_15MIN_MT.len(), 46);
    }
}
