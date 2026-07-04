//! Single-file Feather store: append many poll readings into one `telemetry.feather`.
//!
//! Arrow IPC / Feather is not an in-place append format, so each poll:
//!   1. reads existing rows (if any)
//!   2. concatenates the new samples
//!   3. writes `telemetry.feather.tmp` then renames → `telemetry.feather`
//!
//! Readers only open the completed `.feather` file (never `.tmp`).

use std::fs::File;
use std::path::{Path, PathBuf};
use std::sync::Arc;

use anyhow::{Context, Result};
use arrow::array::{Float64Array, StringArray, TimestampMillisecondArray, UInt32Array};
use arrow::datatypes::{DataType, Field, Schema, TimeUnit};
use arrow::ipc::reader::FileReader;
use arrow::ipc::writer::FileWriter;
use arrow::record_batch::RecordBatch;
use chrono::{DateTime, Utc};

#[derive(Debug, Clone)]
pub struct SampleRow {
    pub ts_utc: DateTime<Utc>,
    /// Human device label (e.g. `BENS-BENCH`, `BensFakeAhu`).
    pub device_name: String,
    pub device_instance: u32,
    pub object_type: String,
    pub object_instance: u32,
    pub point_name: String,
    pub present_value: f64,
    pub units: String,
}

fn schema() -> Schema {
    Schema::new(vec![
        Field::new(
            "ts_utc",
            DataType::Timestamp(TimeUnit::Millisecond, Some("UTC".into())),
            false,
        ),
        Field::new("device_name", DataType::Utf8, false),
        Field::new("device_instance", DataType::UInt32, false),
        Field::new("object_type", DataType::Utf8, false),
        Field::new("object_instance", DataType::UInt32, false),
        Field::new("point_name", DataType::Utf8, false),
        Field::new("present_value", DataType::Float64, false),
        Field::new("units", DataType::Utf8, false),
    ])
}

fn rows_to_batch(rows: &[SampleRow]) -> Result<RecordBatch> {
    let schema = Arc::new(schema());
    let ts: Vec<i64> = rows.iter().map(|r| r.ts_utc.timestamp_millis()).collect();
    let device_names: Vec<&str> = rows.iter().map(|r| r.device_name.as_str()).collect();
    let devices: Vec<u32> = rows.iter().map(|r| r.device_instance).collect();
    let obj_types: Vec<&str> = rows.iter().map(|r| r.object_type.as_str()).collect();
    let obj_inst: Vec<u32> = rows.iter().map(|r| r.object_instance).collect();
    let names: Vec<&str> = rows.iter().map(|r| r.point_name.as_str()).collect();
    let values: Vec<f64> = rows.iter().map(|r| r.present_value).collect();
    let units: Vec<&str> = rows.iter().map(|r| r.units.as_str()).collect();

    RecordBatch::try_new(
        schema,
        vec![
            Arc::new(TimestampMillisecondArray::from(ts).with_timezone("UTC")),
            Arc::new(StringArray::from(device_names)),
            Arc::new(UInt32Array::from(devices)),
            Arc::new(StringArray::from(obj_types)),
            Arc::new(UInt32Array::from(obj_inst)),
            Arc::new(StringArray::from(names)),
            Arc::new(Float64Array::from(values)),
            Arc::new(StringArray::from(units)),
        ],
    )
    .context("building RecordBatch")
}

fn write_all_atomic(path: &Path, rows: &[SampleRow]) -> Result<()> {
    let parent = path.parent().unwrap_or_else(|| Path::new("."));
    std::fs::create_dir_all(parent)
        .with_context(|| format!("creating feather store {}", parent.display()))?;

    let batch = rows_to_batch(rows)?;
    let tmp_path = path.with_extension("feather.tmp");

    {
        let file = File::create(&tmp_path)
            .with_context(|| format!("creating {}", tmp_path.display()))?;
        let mut writer =
            FileWriter::try_new(file, &batch.schema()).context("FileWriter::try_new")?;
        writer.write(&batch).context("FileWriter::write")?;
        writer.finish().context("FileWriter::finish")?;
    }

    std::fs::rename(&tmp_path, path).with_context(|| {
        format!(
            "atomic rename {} -> {}",
            tmp_path.display(),
            path.display()
        )
    })?;
    Ok(())
}

/// Append `rows` into a single Feather file (read-merge-rewrite, atomic).
pub fn append_samples(path: &Path, rows: &[SampleRow]) -> Result<PathBuf> {
    if rows.is_empty() {
        anyhow::bail!("no rows to write");
    }

    let mut all = if path.is_file() {
        match read_samples_from_feather(path) {
            Ok(existing) => existing,
            Err(err) => {
                tracing::warn!(
                    "could not read existing {} ({err:#}) — starting a new file",
                    path.display()
                );
                Vec::new()
            }
        }
    } else {
        Vec::new()
    };

    let prior = all.len();
    all.extend_from_slice(rows);
    write_all_atomic(path, &all)?;
    tracing::info!(
        "appended {} row(s) (prior={prior} total={}) → {}",
        rows.len(),
        all.len(),
        path.display()
    );
    Ok(path.to_path_buf())
}

/// Read all sample rows from a completed `.feather` file.
pub fn read_samples_from_feather(path: &Path) -> Result<Vec<SampleRow>> {
    let file = File::open(path).with_context(|| format!("opening {}", path.display()))?;
    let reader = FileReader::try_new(file, None).context("FileReader::try_new")?;
    let mut out = Vec::new();

    for batch in reader {
        let batch = batch.context("reading record batch")?;
        let ts = batch
            .column_by_name("ts_utc")
            .context("missing ts_utc")?
            .as_any()
            .downcast_ref::<TimestampMillisecondArray>()
            .context("ts_utc type")?;
        let device_names = batch
            .column_by_name("device_name")
            .and_then(|c| c.as_any().downcast_ref::<StringArray>());
        let devices = batch
            .column_by_name("device_instance")
            .context("missing device_instance")?
            .as_any()
            .downcast_ref::<UInt32Array>()
            .context("device_instance type")?;
        let obj_types = batch
            .column_by_name("object_type")
            .context("missing object_type")?
            .as_any()
            .downcast_ref::<StringArray>()
            .context("object_type type")?;
        let obj_inst = batch
            .column_by_name("object_instance")
            .context("missing object_instance")?
            .as_any()
            .downcast_ref::<UInt32Array>()
            .context("object_instance type")?;
        let names = batch
            .column_by_name("point_name")
            .context("missing point_name")?
            .as_any()
            .downcast_ref::<StringArray>()
            .context("point_name type")?;
        let values = batch
            .column_by_name("present_value")
            .context("missing present_value")?
            .as_any()
            .downcast_ref::<Float64Array>()
            .context("present_value type")?;
        let units = batch
            .column_by_name("units")
            .context("missing units")?
            .as_any()
            .downcast_ref::<StringArray>()
            .context("units type")?;

        for i in 0..batch.num_rows() {
            let millis = ts.value(i);
            let ts_utc =
                DateTime::<Utc>::from_timestamp_millis(millis).unwrap_or_else(Utc::now);
            let device_name = device_names
                .map(|a| a.value(i).to_string())
                .unwrap_or_default();
            out.push(SampleRow {
                ts_utc,
                device_name,
                device_instance: devices.value(i),
                object_type: obj_types.value(i).to_string(),
                object_instance: obj_inst.value(i),
                point_name: names.value(i).to_string(),
                present_value: values.value(i),
                units: units.value(i).to_string(),
            });
        }
    }

    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::TimeZone;

    #[test]
    fn append_grows_one_file() {
        let dir = std::env::temp_dir().join(format!(
            "feather_concept_test_{}",
            std::process::id()
        ));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("telemetry.feather");

        let row = |n: i64| SampleRow {
            ts_utc: Utc.timestamp_opt(1_700_000_000 + n, 0).unwrap(),
            device_name: "BENS-BENCH".into(),
            device_instance: 5007,
            object_type: "analog-input".into(),
            object_instance: 1192,
            point_name: "DUCT-T".into(),
            present_value: 70.0 + n as f64,
            units: "°F".into(),
        };

        append_samples(&path, &[row(0)]).unwrap();
        append_samples(&path, &[row(1), row(2)]).unwrap();

        let all = read_samples_from_feather(&path).unwrap();
        assert_eq!(all.len(), 3);
        assert!((all[2].present_value - 72.0).abs() < 1e-9);
        assert_eq!(all[0].device_name, "BENS-BENCH");
        assert_eq!(
            std::fs::read_dir(&dir)
                .unwrap()
                .filter(|e| {
                    e.as_ref()
                        .unwrap()
                        .path()
                        .extension()
                        .is_some_and(|x| x == "feather")
                })
                .count(),
            1
        );

        let _ = std::fs::remove_dir_all(&dir);
    }
}
