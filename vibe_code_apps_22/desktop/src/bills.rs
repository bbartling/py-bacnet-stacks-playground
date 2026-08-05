//! Utility bill CSV loader with industry-style column aliases + guardrails.
//!
//! Fail loud with actionable messages — never silently invent tariff rates.

use std::collections::HashMap;
use std::path::Path;

/// One validated monthly bill row after alias resolution.
#[derive(Clone, Debug)]
pub struct BillRow {
    pub month_key: String, // YYYY-MM
    pub kwh: f32,
    pub cost_usd: f32,
    pub demand_kw: Option<f32>,
    pub billed_demand_kw: Option<f32>,
    #[allow(dead_code)]
    pub days: Option<f32>,
    #[allow(dead_code)]
    pub unit_cost: Option<f32>,
}

#[derive(Clone, Debug)]
pub struct DerivedRates {
    pub energy_rate_per_kwh: f32,
    pub demand_rate_per_kw: f32,
    pub label: String,
    #[allow(dead_code)]
    pub n_rows: usize,
    pub warnings: Vec<String>,
    pub honesty: String,
}

#[derive(Clone, Debug)]
pub struct BillBook {
    pub path: String,
    pub rows: Vec<BillRow>,
    pub warnings: Vec<String>,
    pub heating_season: Option<DerivedRates>,
    pub all_months_ols: Option<DerivedRates>,
}

#[derive(Debug)]
pub struct BillLoadError {
    pub message: String,
}

impl std::fmt::Display for BillLoadError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.message)
    }
}

impl std::error::Error for BillLoadError {}

fn norm_header(h: &str) -> String {
    h.trim()
        .to_ascii_lowercase()
        .chars()
        .filter(|c| c.is_ascii_alphanumeric())
        .collect()
}

/// Map normalized header → logical field.
fn resolve_field(norm: &str) -> Option<&'static str> {
    match norm {
        "month" | "billmonth" => Some("month"),
        "billingperiod" | "period" => Some("billing_period"),
        "billbegin" | "billbegindate" | "begindate" | "startdate" => Some("bill_begin"),
        "billend" | "billenddate" | "enddate" => Some("bill_end"),
        "kwh" | "use" | "kwhtotal" | "usage" | "usagekwh" => Some("kwh"),
        "costusd" | "metercost" | "metercostusd" | "cost" | "totalcost" | "billcost" => {
            Some("cost_usd")
        }
        "demandkw" | "demand" | "peakdemand" | "peakkw" => Some("demand_kw"),
        "billeddemandkw" | "billeddemand" | "billingdemand" => Some("billed_demand_kw"),
        "days" | "nrdays" | "billingdays" => Some("days"),
        "unitcost" | "effectiveunitcost" | "costperkwh" => Some("unit_cost"),
        "account" | "accountnumber" | "useunit" | "useperday" | "billid" | "imageurl"
        | "void" | "accrual" | "flagstatusid" | "flagtype" | "exporthold" | "analyzing"
        | "costunitcodesource" | "costunitsource" | "accrualreversed" => {
            Some("_ignore")
        }
        _ => None,
    }
}

fn parse_f32(raw: &str, field: &str, row: usize) -> Result<Option<f32>, BillLoadError> {
    let t = raw.trim();
    if t.is_empty() {
        return Ok(None);
    }
    let cleaned = t.replace(',', "").replace('$', "");
    cleaned.parse::<f32>().map(Some).map_err(|_| BillLoadError {
        message: format!(
            "Row {row}: cannot parse {field} value '{t}' as a number. \
             Expected plain numeric (commas/$ ok)."
        ),
    })
}

fn month_from_period(period: &str) -> Option<String> {
    let p = period.trim();
    if p.len() == 6 && p.chars().all(|c| c.is_ascii_digit()) {
        return Some(format!("{}-{}", &p[0..4], &p[4..6]));
    }
    if p.len() >= 7 && p.as_bytes().get(4) == Some(&b'-') {
        // YYYY-MM or YYYY-MM-DD
        return Some(p[0..7].to_string());
    }
    None
}

fn calendar_month(yyyy_mm: &str) -> Option<u32> {
    yyyy_mm.split('-').nth(1)?.parse().ok()
}

fn is_heating_month(yyyy_mm: &str) -> bool {
    matches!(calendar_month(yyyy_mm), Some(11 | 12 | 1 | 2 | 3))
}

/// Ordinary least squares: cost ≈ ce * kwh + cd * demand (no intercept).
fn ols_ce_cd(rows: &[&BillRow], demand_field: fn(&BillRow) -> Option<f32>) -> Option<(f32, f32)> {
    // Normal equations for y = a x1 + b x2
    let mut s11 = 0.0_f64;
    let mut s12 = 0.0_f64;
    let mut s22 = 0.0_f64;
    let mut s1y = 0.0_f64;
    let mut s2y = 0.0_f64;
    let mut n = 0usize;
    for r in rows {
        let Some(d) = demand_field(r) else {
            continue;
        };
        if r.kwh <= 0.0 || d <= 0.0 || r.cost_usd <= 0.0 {
            continue;
        }
        let x1 = r.kwh as f64;
        let x2 = d as f64;
        let y = r.cost_usd as f64;
        s11 += x1 * x1;
        s12 += x1 * x2;
        s22 += x2 * x2;
        s1y += x1 * y;
        s2y += x2 * y;
        n += 1;
    }
    if n < 3 {
        return None;
    }
    let det = s11 * s22 - s12 * s12;
    if det.abs() < 1e-9 {
        return None;
    }
    let a = (s1y * s22 - s12 * s2y) / det;
    let b = (s11 * s2y - s12 * s1y) / det;
    Some((a as f32, b as f32))
}

fn guard_rates(ce: f32, cd: f32, label: &str) -> Result<(), BillLoadError> {
    if !(0.02..=0.50).contains(&ce) {
        return Err(BillLoadError {
            message: format!(
                "Derived $/kWh = {ce:.4} for '{label}' is outside industry guardrail \
                 [$0.02, $0.50]. Check that Cost and kWh columns mapped correctly \
                 (Cost must be total $, Use must be kWh — not kW)."
            ),
        });
    }
    if !(0.0..=80.0).contains(&cd) {
        return Err(BillLoadError {
            message: format!(
                "Derived $/kW = {cd:.2} for '{label}' is outside industry guardrail \
                 [$0, $80]. Check Billed Demand vs Demand columns."
            ),
        });
    }
    if ce.is_nan() || cd.is_nan() || ce.is_infinite() || cd.is_infinite() {
        return Err(BillLoadError {
            message: format!("Derived rates for '{label}' are not finite. Check CSV values."),
        });
    }
    Ok(())
}

fn demand_for_fit(r: &BillRow) -> Option<f32> {
    r.billed_demand_kw.or(r.demand_kw)
}

fn make_ols_rates(
    rows: &[BillRow],
    filter: impl Fn(&BillRow) -> bool,
    label: &str,
) -> Result<Option<DerivedRates>, BillLoadError> {
    let subset: Vec<&BillRow> = rows.iter().filter(|r| filter(r)).collect();
    let mut warnings = Vec::new();
    let used_actual = subset.iter().any(|r| r.billed_demand_kw.is_none());
    if used_actual {
        warnings.push(
            "Some rows lack billed_demand_kw — used demand_kw for the fit.".into(),
        );
    }
    let Some((ce, cd)) = ols_ce_cd(&subset, demand_for_fit) else {
        return Ok(None);
    };
    guard_rates(ce, cd, label)?;
    Ok(Some(DerivedRates {
        energy_rate_per_kwh: ce,
        demand_rate_per_kw: cd,
        label: label.to_string(),
        n_rows: subset.len(),
        warnings,
        honesty: format!(
            "OLS from {label} bills: cost ≈ ${ce:.4}/kWh · kWh + ${cd:.2}/kW · billed demand. \
             Engineering proxy — not a full tariff (TOU/ratchet/customer charge omitted)."
        ),
    }))
}

fn rates_from_single_month(row: &BillRow) -> Result<DerivedRates, BillLoadError> {
    let ce = row
        .unit_cost
        .unwrap_or_else(|| row.cost_usd / row.kwh.max(1.0));
    let mut warnings = Vec::new();
    let cd = if let Some(d) = demand_for_fit(row) {
        // Residual after attributing energy at blended unit cost is ~0 by definition.
        // Use a transparent heuristic: demand share ≈ 35% of bill / demand kW
        // when only one month is selected (documented honesty).
        let demand_share = 0.35 * row.cost_usd;
        let est = demand_share / d.max(1.0);
        warnings.push(
            "Single-month demand rate is a 35%-of-bill heuristic (blended unit cost already \
             includes demand). Prefer heating-season OLS when ≥3 winter months are loaded."
                .into(),
        );
        est
    } else {
        warnings.push("No demand column — $/kW set to 0; energy uses Unit Cost / Cost÷kWh.".into());
        0.0
    };
    // For single month, ce is blended — clamp check is looser message
    if !(0.02..=0.50).contains(&ce) {
        return Err(BillLoadError {
            message: format!(
                "Month {}: effective $/kWh = {ce:.4} outside [$0.02, $0.50].",
                row.month_key
            ),
        });
    }
    if cd > 80.0 {
        return Err(BillLoadError {
            message: format!(
                "Month {}: heuristic $/kW = {cd:.2} outside [$0, $80].",
                row.month_key
            ),
        });
    }
    Ok(DerivedRates {
        energy_rate_per_kwh: ce,
        demand_rate_per_kw: cd,
        label: format!("month {}", row.month_key),
        n_rows: 1,
        warnings,
        honesty: format!(
            "Single bill {}: blended ~${ce:.4}/kWh; demand heuristic ${cd:.2}/kW. \
             Prefer multi-month OLS for DSM cost optimization.",
            row.month_key
        ),
    })
}

pub fn load_bill_csv(path: &Path) -> Result<BillBook, BillLoadError> {
    let file = std::fs::File::open(path).map_err(|e| BillLoadError {
        message: format!("Cannot open '{}': {e}", path.display()),
    })?;
    let mut rdr = csv::ReaderBuilder::new()
        .flexible(true)
        .trim(csv::Trim::All)
        .from_reader(file);

    let headers = rdr.headers().map_err(|e| BillLoadError {
        message: format!(
            "CSV has no usable header row in '{}': {e}. \
             Expected columns like month,kwh,cost_usd,billed_demand_kw \
             (or utility aliases: Billing Period, Use, Meter Cost, Billed Demand).",
            path.display()
        ),
    })?;

    let mut col_map: HashMap<String, usize> = HashMap::new();
    let mut unknown = Vec::new();
    for (i, h) in headers.iter().enumerate() {
        let n = norm_header(h);
        if n.is_empty() {
            continue;
        }
        match resolve_field(&n) {
            Some("_ignore") => {}
            Some(logical) => {
                col_map.entry(logical.to_string()).or_insert(i);
            }
            None => unknown.push(h.to_string()),
        }
    }

    let has_month = col_map.contains_key("month")
        || col_map.contains_key("billing_period")
        || col_map.contains_key("bill_begin");
    if !has_month {
        return Err(BillLoadError {
            message: format!(
                "Missing month key. Need one of: month, billing_period / Billing Period, \
                 bill_begin / Bill Begin Date. Found headers: {:?}. Unknown: {:?}",
                headers.iter().collect::<Vec<_>>(),
                unknown
            ),
        });
    }
    if !col_map.contains_key("kwh") {
        return Err(BillLoadError {
            message: "Missing energy column. Need kwh / Use / kWh Total.".into(),
        });
    }
    if !col_map.contains_key("cost_usd") {
        return Err(BillLoadError {
            message: "Missing cost column. Need cost_usd / Meter Cost / cost.".into(),
        });
    }
    if !col_map.contains_key("billed_demand_kw") && !col_map.contains_key("demand_kw") {
        return Err(BillLoadError {
            message: "Missing demand column. Need billed_demand_kw / Billed Demand \
                      (preferred) or demand_kw / Demand."
                .into(),
        });
    }

    let mut warnings = Vec::new();
    if !unknown.is_empty() {
        warnings.push(format!(
            "Ignored unrecognized columns (ok): {}",
            unknown.join(", ")
        ));
    }
    if !col_map.contains_key("billed_demand_kw") {
        warnings.push(
            "No Billed Demand column — using Demand for $/kW fits (ratchet not visible)."
                .into(),
        );
    }

    let mut rows = Vec::new();
    for (idx, rec) in rdr.records().enumerate() {
        let row_num = idx + 2; // header is 1
        let rec = rec.map_err(|e| BillLoadError {
            message: format!("Row {row_num}: CSV parse error: {e}"),
        })?;
        let get = |key: &str| -> &str {
            col_map
                .get(key)
                .and_then(|&i| rec.get(i))
                .unwrap_or("")
        };

        let month_key = if let Some(m) = month_from_period(get("month")) {
            m
        } else if let Some(m) = month_from_period(get("billing_period")) {
            m
        } else if let Some(m) = month_from_period(get("bill_begin")) {
            m
        } else {
            return Err(BillLoadError {
                message: format!(
                    "Row {row_num}: cannot form YYYY-MM from month/billing_period/bill_begin \
                     (got month='{}', period='{}', begin='{}').",
                    get("month"),
                    get("billing_period"),
                    get("bill_begin")
                ),
            });
        };

        let kwh = parse_f32(get("kwh"), "kwh", row_num)?
            .ok_or_else(|| BillLoadError {
                message: format!("Row {row_num}: kwh / Use is empty."),
            })?;
        let cost = parse_f32(get("cost_usd"), "cost", row_num)?
            .ok_or_else(|| BillLoadError {
                message: format!("Row {row_num}: Meter Cost is empty."),
            })?;
        if kwh <= 0.0 {
            return Err(BillLoadError {
                message: format!("Row {row_num} ({month_key}): kwh must be > 0 (got {kwh})."),
            });
        }
        if cost <= 0.0 {
            return Err(BillLoadError {
                message: format!(
                    "Row {row_num} ({month_key}): Meter Cost must be > 0 (got {cost})."
                ),
            });
        }

        let demand_kw = parse_f32(get("demand_kw"), "demand_kw", row_num)?;
        let billed_demand_kw =
            parse_f32(get("billed_demand_kw"), "billed_demand_kw", row_num)?;
        if demand_for_fit(&BillRow {
            month_key: month_key.clone(),
            kwh,
            cost_usd: cost,
            demand_kw,
            billed_demand_kw,
            days: None,
            unit_cost: None,
        })
        .map(|d| d <= 0.0)
        .unwrap_or(true)
        {
            return Err(BillLoadError {
                message: format!(
                    "Row {row_num} ({month_key}): need positive Billed Demand or Demand (kW)."
                ),
            });
        }

        let days = parse_f32(get("days"), "days", row_num)?;
        let unit_cost = parse_f32(get("unit_cost"), "unit_cost", row_num)?;

        rows.push(BillRow {
            month_key,
            kwh,
            cost_usd: cost,
            demand_kw,
            billed_demand_kw,
            days,
            unit_cost,
        });
    }

    if rows.is_empty() {
        return Err(BillLoadError {
            message: "CSV header ok but zero data rows. Export at least one complete bill month."
                .into(),
        });
    }

    rows.sort_by(|a, b| a.month_key.cmp(&b.month_key));

    let heating_season = make_ols_rates(&rows, |r| is_heating_month(&r.month_key), "heating season")?;
    let all_months_ols = make_ols_rates(&rows, |_| true, "all months")?;

    if heating_season.is_none() && all_months_ols.is_none() && rows.len() < 3 {
        warnings.push(
            "Fewer than 3 months — use a single-month preset (heuristic $/kW) until more history is loaded."
                .into(),
        );
    } else if heating_season.is_none() {
        warnings.push(
            "Not enough heating-season months (Nov–Mar) for OLS — use All-months OLS or a single month."
                .into(),
        );
    }

    Ok(BillBook {
        path: path.display().to_string(),
        rows,
        warnings,
        heating_season,
        all_months_ols,
    })
}

impl BillBook {
    pub fn rates_for_month(&self, month_key: &str) -> Result<DerivedRates, BillLoadError> {
        let row = self
            .rows
            .iter()
            .find(|r| r.month_key == month_key)
            .ok_or_else(|| BillLoadError {
                message: format!("No bill row for month '{month_key}'."),
            })?;
        rates_from_single_month(row)
    }

    pub fn default_rates(&self) -> Result<DerivedRates, BillLoadError> {
        if let Some(r) = &self.heating_season {
            return Ok(r.clone());
        }
        if let Some(r) = &self.all_months_ols {
            return Ok(r.clone());
        }
        let last = self.rows.last().ok_or_else(|| BillLoadError {
            message: "Bill book is empty.".into(),
        })?;
        rates_from_single_month(last)
    }
}

/// Prefer env / site utilities, then sample next to the exe (client zip), then repo sample.
pub fn default_bill_csv_candidates() -> Vec<std::path::PathBuf> {
    let mut out = Vec::new();
    if let Ok(p) = std::env::var("LAKESIDE_UTILITY_BILLS_CSV") {
        out.push(std::path::PathBuf::from(p));
    }
    if let Ok(root) = std::env::var("LAKESIDE_SITE_ROOT") {
        let root = std::path::PathBuf::from(root);
        out.push(root.join("utilities").join("electricity_utility_demand.csv"));
        out.push(root.join("utilities").join("utility_bills_raw.csv"));
    }
    // Client package: sample CSV sits beside the .exe
    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            out.push(dir.join("utility_bills_demand_sample.csv"));
        }
    }
    let sample = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("data")
        .join("sample")
        .join("utility_bills_demand_sample.csv");
    out.push(sample);
    out
}

pub fn try_autoload_bills() -> Result<Option<BillBook>, BillLoadError> {
    for p in default_bill_csv_candidates() {
        if p.is_file() {
            return load_bill_csv(&p).map(Some);
        }
    }
    Ok(None)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;

    #[test]
    fn loads_canonical_sample() {
        let p = Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .join("data")
            .join("sample")
            .join("utility_bills_demand_sample.csv");
        if !p.is_file() {
            return;
        }
        let book = load_bill_csv(&p).expect("sample should load");
        assert!(book.rows.len() >= 3);
        let rates = book.default_rates().expect("rates");
        assert!(rates.energy_rate_per_kwh > 0.02);
    }

    #[test]
    fn rejects_missing_cost() {
        let dir = std::env::temp_dir();
        let p = dir.join("bad_bills_lakeside.csv");
        let mut f = std::fs::File::create(&p).unwrap();
        writeln!(f, "month,kwh,demand_kw").unwrap();
        writeln!(f, "2026-01,1000,200").unwrap();
        let err = load_bill_csv(&p).unwrap_err();
        assert!(err.message.contains("cost"));
    }
}
