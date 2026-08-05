//! ONNX Runtime session for heating DSM facility_kw.

use std::path::Path;

use anyhow::{anyhow, bail, Context, Result};
use ort::session::builder::GraphOptimizationLevel;
use ort::session::Session;
use ort::value::Tensor;
use serde::Deserialize;

use crate::features::{scale_features, N_FEATURES};

#[derive(Debug, Deserialize)]
pub struct FeatureMeta {
    pub feature_cols: Vec<String>,
    pub scaler_mean: Vec<f32>,
    pub scaler_scale: Vec<f32>,
    #[serde(default)]
    #[allow(dead_code)]
    pub champion: Option<String>,
    #[serde(default)]
    pub training_source: Option<String>,
    #[serde(default)]
    pub honesty: Option<String>,
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

/// Resolve default artifact paths relative to the exe or CARGO_MANIFEST_DIR.
pub fn default_artifact_paths() -> (std::path::PathBuf, std::path::PathBuf) {
    let candidates = [
        std::env::var_os("LAKESIDE_ONNX_DIR").map(std::path::PathBuf::from),
        std::env::current_exe()
            .ok()
            .and_then(|p| p.parent().map(|d| d.to_path_buf())),
        option_env!("CARGO_MANIFEST_DIR").map(|s| {
            Path::new(s)
                .join("..")
                .join("ml")
                .join("artifacts")
                .canonicalize()
                .unwrap_or_else(|_| Path::new(s).join("..").join("ml").join("artifacts"))
        }),
        Some(Path::new("ml").join("artifacts")),
        Some(Path::new("..").join("ml").join("artifacts")),
    ];

    for base in candidates.into_iter().flatten() {
        let onnx = base.join("heating_dsm_hourly_v1.onnx");
        let meta = base.join("heating_dsm_hourly_v1_feature_meta.json");
        if onnx.is_file() && meta.is_file() {
            return (onnx, meta);
        }
        let onnx2 = base
            .join("ml")
            .join("artifacts")
            .join("heating_dsm_hourly_v1.onnx");
        let meta2 = base
            .join("ml")
            .join("artifacts")
            .join("heating_dsm_hourly_v1_feature_meta.json");
        if onnx2.is_file() && meta2.is_file() {
            return (onnx2, meta2);
        }
    }

    let fallback = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("ml")
        .join("artifacts");
    (
        fallback.join("heating_dsm_hourly_v1.onnx"),
        fallback.join("heating_dsm_hourly_v1_feature_meta.json"),
    )
}
