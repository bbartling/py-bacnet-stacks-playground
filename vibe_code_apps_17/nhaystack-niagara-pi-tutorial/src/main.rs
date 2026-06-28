use anyhow::{Context, Result};
use base64::Engine;
use base64::engine::general_purpose::STANDARD as BASE64;
use clap::Parser;
use reqwest::header::ACCEPT;
use serde::Deserialize;
use std::env;

#[derive(Parser, Debug)]
#[command(about = "Niagara 4.15 nHaystack smoke test (HTTP Basic)")]
struct Args {
    /// Send SCRAM HELLO and print WWW-Authenticate (expect failure on nHaystack)
    #[arg(long)]
    probe_scram: bool,
}

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
    let args = Args::parse();

    let base = env::var("HAYSTACK_BASE")
        .unwrap_or_else(|_| "https://192.168.204.11/haystack".to_string());
    let user = env::var("HAYSTACK_USER").context("Set HAYSTACK_USER")?;
    let pass = env::var("HAYSTACK_PASS").context("Set HAYSTACK_PASS")?;

    let client = reqwest::Client::builder()
        .danger_accept_invalid_certs(true)
        .build()?;

    println!("Station target: {base}");
    println!("User: {user} (expect HTTPBasicScheme in N4 Workbench)");
    println!();

    if args.probe_scram {
        probe_scram_hello(&client, &base, &user).await?;
        println!();
    }

    let about = client
        .get(format!("{base}/about"))
        .basic_auth(&user, Some(&pass))
        .header(ACCEPT, "text/zinc")
        .send()
        .await?
        .error_for_status()?
        .text()
        .await?;

    println!("--- /about (HTTP Basic) ---");
    for line in about.lines().take(6) {
        println!("{line}");
    }
    if about.contains("4.15.3.28") {
        println!("(Niagara 4.15 build confirmed in about grid)");
    }

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
    println!();
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
                row.dis, row.cur_val, row.unit, row.cur_status, row.writable, row.ax_type, row.id,
            );
            println!("  {path}");
        }
    }

    println!();
    println!("Total point/current rows: {count_all}");
    println!("BACnet point/current rows: {count_bacnet}");
    println!();
    println!("Next: ./scripts/03_capture_golden_fixtures.sh  (before Workbench license expires)");

    Ok(())
}

async fn probe_scram_hello(
    client: &reqwest::Client,
    base: &str,
    user: &str,
) -> Result<()> {
    let username_b64 = BASE64.encode(user.as_bytes());
    let nonce = format!(
        "{:016x}",
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_nanos()
    );
    let client_first = BASE64.encode(format!("n={user},r={nonce}").as_bytes());
    let hello = format!("HELLO username={username_b64}, data={client_first}");

    let resp = client
        .get(format!("{base}/about"))
        .header("Authorization", hello)
        .send()
        .await?;

    let www = resp
        .headers()
        .get("www-authenticate")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("<missing>");

    println!("--- SCRAM HELLO probe ---");
    println!("status: {}", resp.status());
    println!("www-authenticate: {www}");
    println!("Niagara nHaystack 3.3 uses HTTP Basic, not Project Haystack SCRAM.");

    Ok(())
}
