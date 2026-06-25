use anyhow::{Context, Result};
use reqwest::header::ACCEPT;
use serde::Deserialize;
use std::env;

#[derive(Debug, Deserialize)]
struct PointRow {
    #[serde(default)]
    dis: String,

    #[serde(default, rename = "curVal")]
    cur_val: String,

    #[serde(default, rename = "curStatus")]
    cur_status: String,

    #[serde(default)]
    unit: String,

    #[serde(default, rename = "axType")]
    ax_type: String,

    #[serde(default, rename = "n4SlotPath")]
    n4_slot_path: String,

    #[serde(default, rename = "axSlotPath")]
    ax_slot_path: String,

    #[serde(default)]
    writable: String,

    #[serde(default)]
    id: String,
}

#[tokio::main]
async fn main() -> Result<()> {
    let base = env::var("HAYSTACK_BASE")
        .unwrap_or_else(|_| "https://192.168.204.11/haystack".to_string());

    let user = env::var("HAYSTACK_USER").context("Set HAYSTACK_USER")?;
    let pass = env::var("HAYSTACK_PASS").context("Set HAYSTACK_PASS")?;

    let client = reqwest::Client::builder()
        // Lab only: Niagara self-signed HTTPS cert.
        .danger_accept_invalid_certs(true)
        .build()?;

    let about = client
        .get(format!("{base}/about"))
        .basic_auth(&user, Some(&pass))
        .header(ACCEPT, "text/zinc")
        .send()
        .await?
        .error_for_status()?
        .text()
        .await?;

    println!("--- /about ---");
    println!("{about}");

    let csv_text = client
        .get(format!("{base}/read"))
        .basic_auth(&user, Some(&pass))
        .header(ACCEPT, "text/csv")
        .query(&[("filter", "point and cur")])
        .send()
        .await?
        .error_for_status()?
        .text()
        .await?;

    std::fs::write("nhaystack_points.csv", &csv_text)?;
    println!("Wrote nhaystack_points.csv");

    let mut rdr = csv::Reader::from_reader(csv_text.as_bytes());
    let mut count_all = 0usize;
    let mut count_bacnet = 0usize;

    println!();
    println!("--- BACnet current-value points ---");

    for result in rdr.deserialize::<PointRow>() {
        let row = result?;
        count_all += 1;

        let path = if !row.n4_slot_path.is_empty() {
            &row.n4_slot_path
        } else {
            &row.ax_slot_path
        };

        if path.contains("/Drivers/BacnetNetwork/") {
            count_bacnet += 1;
            println!(
                "{:<18} {:<18} {:<8} {:<8} writable={} type={} id={}",
                row.dis,
                row.cur_val,
                row.unit,
                row.cur_status,
                row.writable,
                row.ax_type,
                row.id
            );
            println!("  {path}");
        }
    }

    println!();
    println!("Total point/current rows: {count_all}");
    println!("BACnet point/current rows: {count_bacnet}");

    Ok(())
}
