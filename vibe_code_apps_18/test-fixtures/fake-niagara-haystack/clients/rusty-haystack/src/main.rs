use haystack_client::HaystackClient;
use haystack_core::data::{HCol, HDict, HGrid};
use haystack_core::kinds::{HRef, Kind};

fn option(name: &str, default: &str) -> String {
    let args: Vec<String> = std::env::args().collect();
    args.windows(2)
        .find(|pair| pair[0] == name)
        .map(|pair| pair[1].clone())
        .unwrap_or_else(|| default.to_string())
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let url = option("--url", "http://127.0.0.1:8080/api");
    let username = option("--username", "admin");
    let password = option("--password", "demo");
    let range = option("--range", "yesterday");
    let mode = option("--mode", "single");

    let client = HaystackClient::connect(&url, &username, &password).await?;
    let points = client.read("point and his", None).await?;
    let ids: Vec<String> = points
        .iter()
        .filter_map(|row| row.id().map(|id| id.val.clone()))
        .collect();
    if ids.is_empty() {
        return Err("server returned no historized points".into());
    }
    println!("discovered_points={}", ids.len());

    if mode == "single" {
        let history = client.his_read(&ids[0], &range).await?;
        println!("point={}", ids[0]);
        println!("history_rows={}", history.len());
        if history.is_empty() {
            return Err("single-sensor hisRead returned no rows".into());
        }
    } else if mode == "bulk" {
        let mut meta = HDict::new();
        meta.set("range", Kind::Str(range));
        let rows = ids
            .iter()
            .map(|id| {
                let mut row = HDict::new();
                row.set("id", Kind::Ref(HRef::from_val(id)));
                row
            })
            .collect();
        let request = HGrid::from_parts(meta, vec![HCol::new("id")], rows);
        let history = client.call("hisRead", &request).await?;
        let value_cells: usize = history
            .iter()
            .map(|row| row.iter().filter(|(name, _)| *name != "ts").count())
            .sum();
        println!("batch_columns={}", history.num_cols());
        println!("history_rows={}", history.len());
        println!("value_cells={value_cells}");
        if history.num_cols() != ids.len() + 1 || history.is_empty() {
            return Err("batch hisRead returned an unexpected grid shape".into());
        }
    } else {
        return Err(format!("unknown --mode {mode}; use single or bulk").into());
    }

    client.close_session().await?;
    client.close().await?;
    Ok(())
}
