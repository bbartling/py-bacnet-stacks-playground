//! Terminal 2: print new Feather shards as they appear.

use std::collections::HashSet;
use std::path::{Path, PathBuf};
use std::time::Duration;

use anyhow::{Context, Result};
use openfdd_bacnet_feather_concept::app_config::feather_store_folder;
use openfdd_bacnet_feather_concept::feather_store::read_samples_from_feather;
use tracing::{info, warn};

/// Feather tail reader.
///
/// ```text
/// cargo run --bin feather_tail
/// ```
///
/// Scans the store every second. Reads only completed `*.feather` (ignores `*.tmp`).
#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter("info,feather_tail=info")
        .init();

    let root = feather_store_folder();
    std::fs::create_dir_all(&root)
        .with_context(|| format!("creating Feather store folder {}", root.display()))?;

    info!("watching Feather store {}", root.display());
    info!("scan interval: 1 second — only completed .feather files are read");

    let mut seen_files: HashSet<PathBuf> = HashSet::new();

    loop {
        let files = list_completed_feather_files(&root)?;

        for path in files {
            if seen_files.contains(&path) {
                continue;
            }

            match read_samples_from_feather(&path) {
                Ok(samples) => {
                    for sample in samples {
                        println!(
                            "NEW {} device={} {}:{} {}={:.2} {} file={}",
                            sample.ts_utc.to_rfc3339(),
                            sample.device_instance,
                            sample.object_type,
                            sample.object_instance,
                            sample.point_name,
                            sample.present_value,
                            sample.units,
                            path.display(),
                        );
                    }
                    seen_files.insert(path);
                }
                Err(err) => {
                    warn!("could not read {} yet: {err:#}", path.display());
                }
            }
        }

        tokio::time::sleep(Duration::from_secs(1)).await;
    }
}

fn list_completed_feather_files(root: &Path) -> Result<Vec<PathBuf>> {
    let mut files = Vec::new();

    for entry in std::fs::read_dir(root)
        .with_context(|| format!("reading Feather store folder {}", root.display()))?
    {
        let entry = entry?;
        let path = entry.path();
        let is_finished_feather = path
            .extension()
            .and_then(|ext| ext.to_str())
            .is_some_and(|ext| ext.eq_ignore_ascii_case("feather"));
        if is_finished_feather {
            files.push(path);
        }
    }

    files.sort();
    Ok(files)
}
