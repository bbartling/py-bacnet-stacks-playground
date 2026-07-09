use std::path::Path;
use std::time::Instant;

use anyhow::{Context, Result};
use arrow::array::{Float64Array, StringArray, TimestampNanosecondArray};
use arrow::datatypes::{DataType, Field, Schema, TimeUnit};
use arrow::record_batch::RecordBatch;
use parquet::arrow::ArrowWriter;
use serde::Serialize;

use fdd_core::{load_column_role_map, validate_building};

use crate::meta::{meta_path_for, source_fingerprint, write_meta, SidecarMeta};

#[derive(Debug, Clone, Serialize)]
pub struct IngestTiming {
    pub equipment_id: String,
    pub read_ms: u128,
    pub write_ms: u128,
    pub rows: u64,
}

#[derive(Debug, Clone, Serialize)]
pub struct IngestReport {
    pub building_id: String,
    pub out_dir: String,
    pub equipment_written: usize,
    pub total_rows: u64,
    pub timings: Vec<IngestTiming>,
    pub total_ms: u128,
}

pub fn ingest_building(
    data_root: &Path,
    building_id: &str,
    out_dir: &Path,
) -> Result<IngestReport> {
    let started = Instant::now();
    std::fs::create_dir_all(out_dir)?;
    let validation = validate_building(data_root, building_id)?;
    let mut timings = Vec::new();
    let mut total_rows = 0u64;

    for eq in &validation.equipment {
        let t0 = Instant::now();
        let (batch, rows) =
            read_csv_batch(Path::new(&eq.history_path), Path::new(&eq.columns_path))?;
        let read_ms = t0.elapsed().as_millis();

        let dest = out_dir
            .join(format!("building={}", building_id))
            .join(format!("equipment={}", eq.equipment_id));
        std::fs::create_dir_all(&dest)?;
        let parquet_path = dest.join("history.parquet");

        let t1 = Instant::now();
        write_parquet(&parquet_path, &batch)?;
        let write_ms = t1.elapsed().as_millis();

        let src = Path::new(&eq.history_path);
        let (size, mtime, hash) = source_fingerprint(src)?;
        let meta = SidecarMeta {
            building_id: building_id.to_string(),
            equipment_id: eq.equipment_id.clone(),
            source_csv: src.display().to_string(),
            source_size_bytes: size,
            source_modified_unix: mtime,
            source_sha256: hash,
            parquet_path: parquet_path.display().to_string(),
            row_count: rows,
            generated_at: chrono::Utc::now().to_rfc3339(),
        };
        write_meta(&meta_path_for(&parquet_path), &meta)?;

        total_rows += rows;
        timings.push(IngestTiming {
            equipment_id: eq.equipment_id.clone(),
            read_ms,
            write_ms,
            rows,
        });
    }

    Ok(IngestReport {
        building_id: building_id.to_string(),
        out_dir: out_dir.display().to_string(),
        equipment_written: timings.len(),
        total_rows,
        timings,
        total_ms: started.elapsed().as_millis(),
    })
}

fn read_csv_batch(path: &Path, columns_path: &Path) -> Result<(RecordBatch, u64)> {
    let role_map = load_column_role_map(columns_path).unwrap_or_default();
    let mut rdr = csv::Reader::from_path(path).context("csv open")?;
    let headers: Vec<String> = rdr.headers()?.iter().map(|s| s.to_string()).collect();
    let ts_idx = headers
        .iter()
        .position(|h| h == "timestamp_utc" || h == "timestamp")
        .context("timestamp column")?;

    let mut ts_vals: Vec<i64> = Vec::new();
    let mut included: Vec<(usize, String)> = Vec::new();
    let mut used_roles = std::collections::HashSet::new();
    for (i, h) in headers.iter().enumerate() {
        if i == ts_idx {
            continue;
        }
        let Some(role) = role_map.get(h) else {
            continue;
        };
        if !used_roles.insert(role.clone()) {
            continue;
        }
        included.push((i, role.clone()));
    }
    let mut num_cols: Vec<Vec<Option<f64>>> = vec![Vec::new(); included.len()];
    let mut rows = 0u64;

    for rec in rdr.records() {
        let rec = rec?;
        rows += 1;
        let raw_ts = rec.get(ts_idx).unwrap_or("");
        let ts: i64 = chrono::DateTime::parse_from_rfc3339(raw_ts)
            .map(|dt| {
                dt.with_timezone(&chrono::Utc)
                    .timestamp_nanos_opt()
                    .unwrap_or(0)
            })
            .unwrap_or(0);
        ts_vals.push(ts);
        for (j, (i, _)) in included.iter().enumerate() {
            let v = rec.get(*i).and_then(|s| s.parse::<f64>().ok());
            num_cols[j].push(v);
        }
    }

    let mut fields = vec![Field::new(
        "timestamp_utc",
        DataType::Timestamp(TimeUnit::Nanosecond, None),
        false,
    )];
    let mut arrays: Vec<arrow::array::ArrayRef> =
        vec![std::sync::Arc::new(TimestampNanosecondArray::from(ts_vals)) as _];

    for (j, (_, role)) in included.iter().enumerate() {
        fields.push(Field::new(role, DataType::Float64, true));
        let arr = Float64Array::from(num_cols[j].clone());
        arrays.push(std::sync::Arc::new(arr) as _);
    }

    // equipment_id column for SQL joins
    fields.push(Field::new("equipment_id", DataType::Utf8, false));
    let eq_id = path
        .parent()
        .and_then(|p| p.file_name())
        .and_then(|s| s.to_str())
        .unwrap_or("unknown");
    let eq_arr = StringArray::from(vec![eq_id; rows as usize]);
    arrays.push(std::sync::Arc::new(eq_arr) as _);

    let schema = Schema::new(fields);
    let batch = RecordBatch::try_new(std::sync::Arc::new(schema), arrays)?;
    Ok((batch, rows))
}

fn write_parquet(path: &Path, batch: &RecordBatch) -> Result<()> {
    let file = std::fs::File::create(path)?;
    let mut writer = ArrowWriter::try_new(file, batch.schema(), None)?;
    writer.write(batch)?;
    writer.close()?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use tempfile::TempDir;

    #[test]
    fn ingest_writes_parquet_and_meta() {
        let tmp = TempDir::new().unwrap();
        let data = tmp.path().join("BUILDING_100");
        std::fs::create_dir_all(&data).unwrap();
        std::fs::write(data.join("manifest.json"), r#"{"grid_minutes":5}"#).unwrap();
        let ahu = data.join("AHU_1");
        std::fs::create_dir_all(&ahu).unwrap();
        std::fs::write(
            ahu.join("columns.csv"),
            "col,point_role\nfan_speed_pct,fan_cmd\n",
        )
        .unwrap();
        let mut f = std::fs::File::create(ahu.join("history_wide.csv")).unwrap();
        writeln!(f, "timestamp_utc,fan_speed_pct").unwrap();
        writeln!(f, "2026-01-01T00:00:00Z,1.0").unwrap();
        writeln!(f, "2026-01-01T00:05:00Z,2.0").unwrap();

        let out = tmp.path().join("parquet");
        let report = ingest_building(tmp.path(), "BUILDING_100", &out).unwrap();
        assert_eq!(report.equipment_written, 1);
        assert_eq!(report.total_rows, 2);
        let pq = out.join("building=BUILDING_100/equipment=AHU_1/history.parquet");
        assert!(pq.is_file());
        assert!(meta_path_for(&pq).is_file());
    }
}
