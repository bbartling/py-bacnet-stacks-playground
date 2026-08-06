//! ONNX Runtime session for heating DSM facility_kw.

use std::collections::BTreeMap;
use std::path::Path;

use anyhow::{anyhow, bail, Context, Result};
use ort::session::builder::GraphOptimizationLevel;
use ort::session::Session;
use ort::value::Tensor;
use serde::Deserialize;

use crate::features::{scale_features, N_FEATURES};

#[derive(Debug, Clone, Deserialize, Default)]
pub struct CvMetrics {
    #[serde(default)]
    pub mae: Option<f32>,
    #[serde(default)]
    pub rmse: Option<f32>,
    #[serde(default)]
    pub mae_peak_05_09: Option<f32>,
    #[serde(default)]
    pub rmse_peak_05_09: Option<f32>,
}

#[derive(Debug, Deserialize)]
pub struct FeatureMeta {
    pub feature_cols: Vec<String>,
    pub scaler_mean: Vec<f32>,
    pub scaler_scale: Vec<f32>,
    #[serde(default)]
    pub model_name: Option<String>,
    #[serde(default)]
    pub champion: Option<String>,
    #[serde(default)]
    pub family: Option<String>,
    #[serde(default)]
    pub model_backend: Option<String>,
    #[serde(default)]
    pub training_source: Option<String>,
    #[serde(default)]
    pub honesty: Option<String>,
    #[serde(default)]
    pub cv_mae_peak_05_09: Option<f32>,
    #[serde(default)]
    pub precision_pm_kw: Option<f32>,
    #[serde(default)]
    pub precision_note: Option<String>,
    #[serde(default)]
    pub cv_metrics: Option<CvMetrics>,
    /// Tuned hyperparameters (JSON numbers/strings/bools).
    #[serde(default)]
    pub best_params: BTreeMap<String, serde_json::Value>,
}

impl FeatureMeta {
    pub fn display_name(&self) -> String {
        self.model_name
            .clone()
            .or_else(|| self.champion.clone())
            .unwrap_or_else(|| "unknown".into())
    }

    pub fn precision_pm(&self) -> f32 {
        self.precision_pm_kw
            .or(self.cv_metrics.as_ref().and_then(|c| c.mae_peak_05_09))
            .or(self.cv_mae_peak_05_09)
            .unwrap_or(0.0)
    }

    pub fn banner_line(&self) -> String {
        let name = self.display_name();
        let family = self.family.as_deref().unwrap_or("sklearn");
        let src = self.training_source.as_deref().unwrap_or("?");
        let backend = self.model_backend.as_deref().unwrap_or("onnx");
        let pm = self.precision_pm();
        format!("{family} · {name} · {backend} · {src} · ±{pm:.1} kW")
    }

    pub fn metrics_lines(&self) -> Vec<String> {
        let cv = self.cv_metrics.clone().unwrap_or_default();
        let mae = cv.mae.unwrap_or(0.0);
        let rmse = cv.rmse.unwrap_or(0.0);
        let mae_p = cv
            .mae_peak_05_09
            .or(self.cv_mae_peak_05_09)
            .unwrap_or(mae);
        let rmse_p = cv.rmse_peak_05_09.unwrap_or(rmse);
        let pm = self.precision_pm();
        vec![
            format!("All-hours   MAE {mae:.2}   RMSE {rmse:.2} kW"),
            format!("Peak HE05–09 MAE {mae_p:.2}   RMSE {rmse_p:.2} kW"),
            format!("Walk band   ±{pm:.1} kW  (peak MAE screening)"),
        ]
    }

    pub fn params_sorted(&self) -> Vec<(String, String)> {
        self.best_params
            .iter()
            .map(|(k, v)| {
                let s = match v {
                    serde_json::Value::Null => "null".into(),
                    serde_json::Value::Bool(b) => b.to_string(),
                    serde_json::Value::Number(n) => n.to_string(),
                    serde_json::Value::String(s) => s.clone(),
                    other => other.to_string(),
                };
                (k.clone(), s)
            })
            .collect()
    }
}

pub struct OnnxModel {
    session: Session,
    pub meta: FeatureMeta,
}

fn ort_err(e: impl std::fmt::Display) -> anyhow::Error {
    anyhow!("{e}")
}

impl OnnxModel {
    pub fn load(onnx_path: &Path, meta_path: &Path) -> Result<Self> {
        let meta_txt = std::fs::read_to_string(meta_path)
            .with_context(|| format!("read feature meta {}", meta_path.display()))?;
        let meta: FeatureMeta =
            serde_json::from_str(&meta_txt).context("parse feature_meta.json")?;
        if meta.scaler_mean.len() != N_FEATURES || meta.scaler_scale.len() != N_FEATURES {
            bail!(
                "scaler length {} / {} expected {}",
                meta.scaler_mean.len(),
                meta.scaler_scale.len(),
                N_FEATURES
            );
        }
        if meta.feature_cols.len() != N_FEATURES {
            bail!(
                "feature_cols length {} expected {}",
                meta.feature_cols.len(),
                N_FEATURES
            );
        }

        let session = Session::builder()
            .map_err(ort_err)?
            .with_optimization_level(GraphOptimizationLevel::Level3)
            .map_err(ort_err)?
            .commit_from_file(onnx_path)
            .map_err(ort_err)
            .with_context(|| format!("load ONNX {}", onnx_path.display()))?;

        Ok(Self { session, meta })
    }

    pub fn predict_kw(&mut self, raw_features: &[f32; N_FEATURES]) -> Result<f32> {
        let scaled = scale_features(
            raw_features,
            &self.meta.scaler_mean,
            &self.meta.scaler_scale,
        );
        let input = Tensor::from_array(([1usize, N_FEATURES], scaled.to_vec())).map_err(ort_err)?;
        let outputs = self
            .session
            .run(ort::inputs!["features" => input])
            .map_err(ort_err)?;
        let (_shape, data) = outputs["facility_kw"]
            .try_extract_tensor::<f32>()
            .map_err(ort_err)?;
        Ok(data[0])
    }
}

/// Resolve default artifact paths — hybrid 15-min stems only (hourly quarantined).
pub fn default_artifact_paths() -> (std::path::PathBuf, std::path::PathBuf) {
    let candidates = [
        std::env::var_os("LAKESIDE_ONNX_DIR").map(std::path::PathBuf::from),
        std::env::current_exe()
            .ok()
            .and_then(|p| p.parent().map(|d| d.to_path_buf())),
        option_env!("CARGO_MANIFEST_DIR").map(|s| Path::new(s).join("artifacts")),
        option_env!("CARGO_MANIFEST_DIR").map(|s| {
            Path::new(s)
                .join("..")
                .join("ml")
                .join("artifacts")
        }),
        Some(Path::new("ml").join("artifacts")),
        Some(Path::new("..").join("ml").join("artifacts")),
    ];

    for base in candidates.into_iter().flatten() {
        let onnx = base.join("real_baseline_15min_v1.onnx");
        let meta = base.join("real_baseline_15min_v1_feature_meta.json");
        if onnx.is_file() && meta.is_file() {
            return (onnx, meta);
        }
    }

    let fallback = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("ml")
        .join("artifacts");
    (
        fallback.join("real_baseline_15min_v1.onnx"),
        fallback.join("real_baseline_15min_v1_feature_meta.json"),
    )
}
