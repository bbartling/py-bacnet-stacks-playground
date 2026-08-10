//! Hybrid ship manifest — notebook promote output (champions + G14 precision).

use std::fs;
use std::path::{Path, PathBuf};

use serde::Deserialize;

#[derive(Debug, Clone, Default, Deserialize)]
pub struct G14Reference {
    pub nmbe_abs_max: Option<f64>,
    pub cv_rmse_max: Option<f64>,
    pub note: Option<String>,
}

#[derive(Debug, Clone, Default, Deserialize)]
pub struct MvArmMetrics {
    pub nmbe: Option<f64>,
    pub cv_rmse: Option<f64>,
    pub mae: Option<f64>,
    pub mae_peak_05_09: Option<f64>,
    pub zone_temp_mae_mean: Option<f64>,
}

#[derive(Debug, Clone, Default, Deserialize)]
pub struct MvPrecision {
    pub precision_pm_kw: Option<f32>,
    pub precision_label: Option<String>,
    pub g14_monthly_reference: Option<G14Reference>,
    pub champion_baseline: Option<String>,
    pub champion_delta: Option<String>,
    #[serde(default)]
    pub baseline: MvArmMetrics,
    #[serde(default)]
    pub delta: MvArmMetrics,
}

#[derive(Debug, Clone, Default, Deserialize)]
pub struct ShipManifest {
    pub ship_mode: Option<String>,
    pub honesty: Option<String>,
    pub champion_baseline: Option<String>,
    pub champion_delta: Option<String>,
    pub watermark: Option<String>,
    pub honesty_note: Option<String>,
    pub outcome_flag: Option<String>,
    pub pair_count: Option<i64>,
    pub mv_precision: Option<MvPrecision>,
}

fn candidate_manifest_paths() -> Vec<PathBuf> {
    let mut out = Vec::new();
    if let Some(dir) = std::env::var_os("LAKESIDE_ONNX_DIR") {
        out.push(PathBuf::from(dir).join("hybrid_ship_manifest.json"));
    }
    if let Ok(exe) = std::env::current_exe() {
        if let Some(d) = exe.parent() {
            out.push(d.join("hybrid_ship_manifest.json"));
            out.push(d.join("artifacts").join("hybrid_ship_manifest.json"));
        }
    }
    if let Some(manifest) = option_env!("CARGO_MANIFEST_DIR") {
        let m = Path::new(manifest);
        out.push(m.join("artifacts").join("hybrid_ship_manifest.json"));
        out.push(
            m.join("..")
                .join("ml")
                .join("artifacts")
                .join("hybrid_ship_manifest.json"),
        );
    }
    out
}

pub fn load_ship_manifest() -> Option<(ShipManifest, PathBuf)> {
    for path in candidate_manifest_paths() {
        if !path.is_file() {
            continue;
        }
        let txt = fs::read_to_string(&path).ok()?;
        match serde_json::from_str::<ShipManifest>(&txt) {
            Ok(m) => return Some((m, path)),
            Err(_) => continue,
        }
    }
    None
}

fn pct(frac: Option<f64>) -> Option<String> {
    frac.map(|v| format!("{:.1}%", v * 100.0))
}

/// Build UI metric lines + screening +/- from notebook ship manifest.
pub fn metrics_from_manifest(ship: &ShipManifest) -> (Vec<String>, f32, String) {
    let mut lines = Vec::new();
    let mv = ship.mv_precision.as_ref();

    let champ_b = ship
        .champion_baseline
        .as_deref()
        .or_else(|| mv.and_then(|m| m.champion_baseline.as_deref()))
        .unwrap_or("?");
    let champ_d = ship
        .champion_delta
        .as_deref()
        .or_else(|| mv.and_then(|m| m.champion_delta.as_deref()))
        .unwrap_or("?");
    lines.push(format!(
        "Selected (notebook promote): baseline={champ_b} · delta={champ_d}"
    ));

    if let Some(mode) = &ship.ship_mode {
        lines.push(format!("ship_mode={mode}"));
    }
    if let Some(w) = &ship.watermark {
        lines.push(format!("watermark: {w}"));
    }
    if let Some(note) = &ship.honesty_note {
        lines.push(note.clone());
    }

    if let Some(mv) = mv {
        let b = &mv.baseline;
        let mut primary = String::from("Baseline held-out (G14 primary):");
        if let Some(s) = pct(b.nmbe) {
            primary.push_str(&format!(" NMBE={s}"));
        }
        if let Some(s) = pct(b.cv_rmse) {
            primary.push_str(&format!(" CV(RMSE)={s}"));
        }
        lines.push(primary);

        let mut secondary = String::from("Baseline secondary:");
        if let Some(mae) = b.mae {
            secondary.push_str(&format!(" MAE={mae:.2} kW"));
        }
        if let Some(peak) = b.mae_peak_05_09 {
            secondary.push_str(&format!(" peakMAE={peak:.2} kW"));
        }
        if let Some(z) = b.zone_temp_mae_mean {
            secondary.push_str(&format!(" zoneMAE={z:.2} degF"));
        }
        lines.push(secondary);

        let d = &mv.delta;
        let mut dline = String::from("Delta held-out:");
        if let Some(s) = pct(d.nmbe) {
            dline.push_str(&format!(" NMBE={s}"));
        }
        if let Some(s) = pct(d.cv_rmse) {
            dline.push_str(&format!(" CV(RMSE)={s}"));
        }
        if let Some(mae) = d.mae {
            dline.push_str(&format!(" MAE={mae:.2} kW"));
        }
        lines.push(dline);

        if let Some(g14) = &mv.g14_monthly_reference {
            if let Some(note) = &g14.note {
                lines.push(note.clone());
            } else {
                lines.push(format!(
                    "G14 monthly ref: |NMBE|<={:.0}% CV(RMSE)<={:.0}% (context only)",
                    g14.nmbe_abs_max.unwrap_or(0.05) * 100.0,
                    g14.cv_rmse_max.unwrap_or(0.15) * 100.0
                ));
            }
        }
    }

    lines.push(
        "Honesty: HYBRID_SCREENING · IdealLoads + fixed-COP (not GSHP) — filename gshp is naming only"
            .into(),
    );
    if is_smoke_screening(ship) {
        lines.push("Smoke/screening farm — operational DSM recommendations disabled".into());
    }
    if let Some(flag) = &ship.outcome_flag {
        lines.push(format!("outcome_flag: {flag}"));
    }

    let pm = mv.and_then(|m| m.precision_pm_kw).unwrap_or(0.0);
    let note = mv
        .and_then(|m| m.precision_label.clone())
        .unwrap_or_else(|| {
            "screening +/- from held-out peak MAE when promote writes mv_precision".into()
        });
    (lines, pm, note)
}

/// Smoke / underpowered farm — refuse recommendation language (acceptance policy).
pub fn is_smoke_screening(ship: &ShipManifest) -> bool {
    if ship.ship_mode.as_deref() == Some("smoke_artifact") {
        return true;
    }
    if let Some(w) = ship.watermark.as_deref() {
        let u = w.to_ascii_uppercase();
        if u.contains("SMOKE") || u.contains("UNDERPOWERED") {
            return true;
        }
    }
    if let Some(n) = ship.pair_count {
        if n >= 0 && n < 12 {
            return true;
        }
    }
    false
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_mv_precision_block() {
        let raw = r#"{
            "ship_mode": "smoke_artifact",
            "champion_baseline": "extra_trees",
            "champion_delta": "gradient_boosting",
            "watermark": "UNDERPOWERED_SMOKE_FARM",
            "pair_count": 6,
            "mv_precision": {
                "primary": ["nmbe", "cv_rmse"],
                "precision_pm_kw": 12.5,
                "precision_label": "screening",
                "baseline": {"nmbe": 0.04, "cv_rmse": 0.18, "mae": 10.0},
                "delta": {"nmbe": -0.02, "cv_rmse": 0.2},
                "g14_monthly_reference": {"nmbe_abs_max": 0.05, "cv_rmse_max": 0.15, "note": "ref"}
            }
        }"#;
        let ship: ShipManifest = serde_json::from_str(raw).unwrap();
        let (lines, pm, note) = metrics_from_manifest(&ship);
        assert!((pm - 12.5).abs() < 1e-6);
        assert_eq!(note, "screening");
        assert!(lines.iter().any(|l| l.contains("extra_trees")));
        assert!(lines.iter().any(|l| l.contains("NMBE=")));
        assert!(lines.iter().any(|l| l.contains("CV(RMSE)=")));
        assert!(lines.iter().any(|l| l.contains("IdealLoads + fixed-COP")));
        assert!(is_smoke_screening(&ship));
    }

    #[test]
    fn smoke_screening_from_pair_count() {
        let ship = ShipManifest {
            pair_count: Some(6),
            ..Default::default()
        };
        assert!(is_smoke_screening(&ship));
        let ship2 = ShipManifest {
            pair_count: Some(24),
            ship_mode: Some("full".into()),
            ..Default::default()
        };
        assert!(!is_smoke_screening(&ship2));
    }
}
