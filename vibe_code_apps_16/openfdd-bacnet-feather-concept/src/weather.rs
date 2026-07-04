//! Open-Meteo outdoor weather → shared app state (BACnet AVs).
//!
//! Polls geocoding + forecast on a slow interval (default 20 min). On failure,
//! applies configured fallback values. Dewpoint is calculated from dry-bulb + RH
//! when the forecast does not include it (Magnus-Tetens).

use std::path::PathBuf;
use std::sync::Arc;
use std::time::{Duration, Instant};

use anyhow::{anyhow, Context, Result};
use chrono::Utc;
use serde::Deserialize;
use tokio::sync::Mutex;
use tracing::{info, warn};

use crate::app_config::WeatherConfig;
use crate::feather_store::{append_samples, SampleRow};
use crate::latest::{AppStateHandle, WeatherReading};

#[derive(Debug, Deserialize)]
struct GeocodeResponse {
    results: Option<Vec<GeocodeLocation>>,
}

#[derive(Debug, Clone, Deserialize)]
struct GeocodeLocation {
    name: String,
    #[serde(default)]
    admin1: Option<String>,
    country: String,
    latitude: f64,
    longitude: f64,
    #[serde(default)]
    timezone: Option<String>,
}

#[derive(Debug, Deserialize)]
struct WeatherResponse {
    current: CurrentWeather,
}

#[derive(Debug, Deserialize)]
struct CurrentWeather {
    #[serde(rename = "temperature_2m")]
    temperature_2m: f64,
    #[serde(rename = "relative_humidity_2m")]
    relative_humidity_2m: Option<f64>,
    #[serde(rename = "wind_speed_10m")]
    wind_speed_10m: Option<f64>,
    /// Present in some Open-Meteo responses; we always recompute as a check.
    #[serde(rename = "dew_point_2m")]
    dew_point_2m: Option<f64>,
}

/// Outdoor dewpoint (°F) from dry-bulb (°F) and relative humidity (%).
///
/// Magnus-Tetens approximation (useful for economizer / free-cooling logic when
/// the forecast does not include dewpoint).
pub fn dewpoint_f_from_db_rh(temp_f: f64, rh_percent: f64) -> f64 {
    let t_c = (temp_f - 32.0) * 5.0 / 9.0;
    let rh = rh_percent.clamp(0.1, 100.0);
    let a = 17.27_f64;
    let b = 237.7_f64;
    let alpha = (a * t_c) / (b + t_c) + (rh / 100.0).ln();
    let dp_c = (b * alpha) / (a - alpha);
    dp_c * 9.0 / 5.0 + 32.0
}

fn fallback_reading(cfg: &WeatherConfig, reason: &str) -> WeatherReading {
    let dewpoint_f = dewpoint_f_from_db_rh(cfg.fallback_temp_f, cfg.fallback_humidity);
    WeatherReading {
        temp_f: cfg.fallback_temp_f,
        humidity: cfg.fallback_humidity,
        wind_mph: cfg.fallback_wind_mph,
        dewpoint_f,
        from_api: false,
        location: format!("{} (fallback)", cfg.city),
        reason: reason.into(),
        fetched_at: Instant::now(),
    }
}

async fn geocode_search(
    client: &reqwest::Client,
    name: &str,
    count: u32,
) -> Result<Vec<GeocodeLocation>> {
    let encoded = urlencoding::encode(name.trim());
    let url = format!(
        "https://geocoding-api.open-meteo.com/v1/search?name={encoded}&count={count}&language=en&format=json"
    );
    let response: GeocodeResponse = client
        .get(&url)
        .send()
        .await
        .context("Open-Meteo geocoding request")?
        .error_for_status()
        .context("Open-Meteo geocoding HTTP error")?
        .json()
        .await
        .context("Open-Meteo geocoding JSON")?;
    Ok(response.results.unwrap_or_default())
}

/// Resolve a free-text city (e.g. `"Madison Wisconsin"`).
///
/// Open-Meteo often returns no hits for multi-word queries, so we:
/// 1. try the full string
/// 2. search the first token and prefer a result whose `admin1` matches the rest
async fn geocode_city(client: &reqwest::Client, city: &str) -> Result<GeocodeLocation> {
    let city = city.trim();
    let cleaned = city.replace(',', " ");
    let parts: Vec<&str> = cleaned.split_whitespace().collect();

    let mut results = geocode_search(client, city, 1).await?;
    if let Some(loc) = results.pop() {
        return Ok(loc);
    }

    if parts.len() >= 2 {
        let name = parts[0];
        let admin_hint = parts[1..].join(" ").to_ascii_lowercase();
        let candidates = geocode_search(client, name, 10).await?;
        if let Some(loc) = candidates.iter().find(|c| {
            c.admin1
                .as_deref()
                .map(|a| {
                    let a = a.to_ascii_lowercase();
                    a == admin_hint || admin_hint.contains(&a) || a.contains(&admin_hint)
                })
                .unwrap_or(false)
        }) {
            return Ok(loc.clone());
        }
        if let Some(loc) = candidates.into_iter().next() {
            return Ok(loc);
        }
    } else if let Some(loc) = geocode_search(client, city, 1).await?.into_iter().next() {
        return Ok(loc);
    }

    Err(anyhow!("no geocode result for city '{city}'"))
}

async fn fetch_current(
    client: &reqwest::Client,
    location: &GeocodeLocation,
) -> Result<WeatherResponse> {
    let timezone = location
        .timezone
        .clone()
        .unwrap_or_else(|| "auto".into());
    let url = format!(
        "https://api.open-meteo.com/v1/forecast\
?latitude={}\
&longitude={}\
&current=temperature_2m,relative_humidity_2m,wind_speed_10m,dew_point_2m\
&temperature_unit=fahrenheit\
&wind_speed_unit=mph\
&timezone={}",
        location.latitude,
        location.longitude,
        urlencoding::encode(&timezone)
    );
    client
        .get(&url)
        .send()
        .await
        .context("Open-Meteo forecast request")?
        .error_for_status()
        .context("Open-Meteo forecast HTTP error")?
        .json()
        .await
        .context("Open-Meteo forecast JSON")
}

async fn poll_once(client: &reqwest::Client, cfg: &WeatherConfig) -> WeatherReading {
    match geocode_city(client, &cfg.city).await {
        Ok(location) => match fetch_current(client, &location).await {
            Ok(weather) => {
                let temp_f = weather.current.temperature_2m;
                let humidity = weather
                    .current
                    .relative_humidity_2m
                    .unwrap_or(cfg.fallback_humidity);
                let wind_mph = weather
                    .current
                    .wind_speed_10m
                    .unwrap_or(cfg.fallback_wind_mph);
                // Prefer calculated dewpoint for economizer consistency; use API if calc fails.
                let dewpoint_f = if humidity > 0.0 {
                    dewpoint_f_from_db_rh(temp_f, humidity)
                } else {
                    weather
                        .current
                        .dew_point_2m
                        .unwrap_or_else(|| dewpoint_f_from_db_rh(temp_f, cfg.fallback_humidity))
                };
                let location_label = format!(
                    "{}, {}, {}",
                    location.name,
                    location.admin1.unwrap_or_default(),
                    location.country
                );
                info!(
                    "weather ok {location_label}: T={temp_f:.1}°F RH={humidity:.0}% wind={wind_mph:.1}mph DP={dewpoint_f:.1}°F"
                );
                WeatherReading {
                    temp_f,
                    humidity,
                    wind_mph,
                    dewpoint_f,
                    from_api: true,
                    location: location_label,
                    reason: "ok".into(),
                    fetched_at: Instant::now(),
                }
            }
            Err(err) => {
                warn!("weather forecast failed: {err:#} — using fallbacks");
                fallback_reading(cfg, &format!("forecast: {err:#}"))
            }
        },
        Err(err) => {
            warn!("weather geocode failed: {err:#} — using fallbacks");
            fallback_reading(cfg, &format!("geocode: {err:#}"))
        }
    }
}

/// Rows for one Open-Meteo scrape (numeric AV mirrors only).
pub fn reading_to_sample_rows(cfg: &WeatherConfig, reading: &WeatherReading) -> Vec<SampleRow> {
    let ts = Utc::now();
    let device_name = format!("Open-Meteo-{}", cfg.city);
    vec![
        SampleRow {
            ts_utc: ts,
            device_name: device_name.clone(),
            device_instance: 0,
            object_type: "analog-value".into(),
            object_instance: cfg.temp_object_instance,
            point_name: cfg.temp_point_name.clone(),
            present_value: reading.temp_f,
            units: "°F".into(),
        },
        SampleRow {
            ts_utc: ts,
            device_name: device_name.clone(),
            device_instance: 0,
            object_type: "analog-value".into(),
            object_instance: cfg.humidity_object_instance,
            point_name: cfg.humidity_point_name.clone(),
            present_value: reading.humidity,
            units: "%RH".into(),
        },
        SampleRow {
            ts_utc: ts,
            device_name: device_name.clone(),
            device_instance: 0,
            object_type: "analog-value".into(),
            object_instance: cfg.wind_object_instance,
            point_name: cfg.wind_point_name.clone(),
            present_value: reading.wind_mph,
            units: "mph".into(),
        },
        SampleRow {
            ts_utc: ts,
            device_name,
            device_instance: 0,
            object_type: "analog-value".into(),
            object_instance: cfg.dewpoint_object_instance,
            point_name: cfg.dewpoint_point_name.clone(),
            present_value: reading.dewpoint_f,
            units: "°F".into(),
        },
    ]
}

async fn append_weather_to_feather(
    store_path: &PathBuf,
    feather_lock: &Arc<Mutex<()>>,
    cfg: &WeatherConfig,
    reading: &WeatherReading,
) {
    if !reading.from_api {
        return;
    }
    let rows = reading_to_sample_rows(cfg, reading);
    let _guard = feather_lock.lock().await;
    match append_samples(store_path, &rows) {
        Ok(_) => info!(
            "weather feather +{} row(s) Open-Meteo {} → {}",
            rows.len(),
            reading.location,
            store_path.display()
        ),
        Err(err) => warn!("weather feather append failed: {err:#}"),
    }
}

/// Background task: apply fallbacks immediately, then refresh on `interval_secs`.
pub async fn run_weather_forever(
    cfg: WeatherConfig,
    store_path: PathBuf,
    feather_lock: Arc<Mutex<()>>,
    state: AppStateHandle,
) {
    if !cfg.enabled {
        info!("weather.enabled=false — outdoor weather AVs stay at fallback defaults");
        let reading = fallback_reading(&cfg, "disabled");
        state.write().await.weather = Some(reading);
        return;
    }

    let interval = Duration::from_secs(cfg.interval_secs.max(60));
    info!(
        "weather poller city=\"{}\" interval={}s (Open-Meteo)",
        cfg.city,
        interval.as_secs()
    );

    // Seed fallbacks so BACnet points are never empty before first API call.
    {
        let reading = fallback_reading(&cfg, "startup fallback");
        state.write().await.weather = Some(reading);
    }

    let client = match reqwest::Client::builder()
        .timeout(Duration::from_secs(20))
        .user_agent(concat!(
            "openfdd-bacnet-feather-concept/",
            env!("CARGO_PKG_VERSION")
        ))
        .build()
    {
        Ok(c) => c,
        Err(err) => {
            warn!("weather HTTP client build failed: {err} — staying on fallbacks");
            loop {
                tokio::time::sleep(interval).await;
            }
        }
    };

    loop {
        let reading = poll_once(&client, &cfg).await;
        state.write().await.weather = Some(reading.clone());
        append_weather_to_feather(&store_path, &feather_lock, &cfg, &reading).await;
        tokio::time::sleep(interval).await;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn dewpoint_reasonable_for_room_conditions() {
        // 70°F @ 50% RH → dewpoint roughly mid-40s to low-50s °F
        let dp = dewpoint_f_from_db_rh(70.0, 50.0);
        assert!(dp > 45.0 && dp < 55.0, "dp={dp}");
    }

    #[test]
    fn dewpoint_at_100_rh_near_dry_bulb() {
        let dp = dewpoint_f_from_db_rh(60.0, 100.0);
        assert!((dp - 60.0).abs() < 0.5, "dp={dp}");
    }
}
