//! Minimal Turtle loader + export stub for RDF-in-Rust capstone (Days 66, 68, 75).

use anyhow::{Context, Result};
use clap::Parser;
use std::collections::HashSet;
use std::fs;
use std::path::PathBuf;

#[derive(Parser)]
#[command(name = "graph-export", about = "Load TTL, count triples, export merged Turtle (capstone skeleton)")]
struct Cli {
    #[arg(long, default_value = "../model/ahu1.ttl")]
    ttl: PathBuf,
    #[arg(long, default_value = "merged.ttl")]
    out: PathBuf,
    /// Stub: pretend BACnet read updated this literal (Day 68 exercise)
    #[arg(long)]
    stub_pv: Option<f64>,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let raw = fs::read_to_string(&cli.ttl).with_context(|| format!("read {}", cli.ttl.display()))?;
    let triples = parse_turtle_lite(&raw);
    eprintln!("loaded {} triple-ish lines from {}", triples.len(), cli.ttl.display());

    let mut out = String::new();
    out.push_str("# merged export — graph-export capstone\n");
    out.push_str(&raw);
    if let Some(pv) = cli.stub_pv {
        out.push_str("\n# Day 68 stub live value\n");
        out.push_str(&format!(
            "ex:OA-T ex:curVal \"{pv}\"^^xsd:double .\n"
        ));
    }

    if let Some(parent) = cli.out.parent() {
        if !parent.as_os_str().is_empty() {
            fs::create_dir_all(parent)?;
        }
    }
    fs::write(&cli.out, &out).with_context(|| format!("write {}", cli.out.display()))?;
    eprintln!("wrote {}", cli.out.display());
    eprintln!("next: replace stub with rusty-bacnet read → triple update (Day 68)");
    Ok(())
}

/// Very small parser: non-empty, non-comment lines ending in `.`
fn parse_turtle_lite(ttl: &str) -> Vec<String> {
    let mut set = HashSet::new();
    for line in ttl.lines() {
        let t = line.trim();
        if t.is_empty() || t.starts_with('#') || t.starts_with('@') {
            continue;
        }
        if t.contains('.') {
            set.insert(t.to_string());
        }
    }
    set.into_iter().collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn counts_ahu_triples() {
        let ttl = include_str!("../../model/ahu1.ttl");
        let t = parse_turtle_lite(ttl);
        assert!(!t.is_empty(), "expected triple lines in ahu1.ttl");
    }
}
