"""Open-Meteo Archive API downloader for actual-year (AMY) hourly weather.

Downloads hourly weather from ``archive-api.open-meteo.com/v1/archive`` in
Fahrenheit / mph / UTC, validates the response against the requesting
:class:`~wattlab.contracts.WeatherRequest` (coordinates, date span, array
shapes, hourly timestamps, physical bounds, units, annual coverage), maps it
to the column names :func:`wattlab.weather.epw.build_amy_epw` consumes, and
caches an envelope (request metadata + downloaded_at_utc + response) atomically.

No network access happens in unit tests: ``opener`` is dependency-injected
and receives the request URL, returning raw response bytes.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode

import pandas as pd

from wattlab.contracts import WeatherDatasetMeta, WeatherRequest
from wattlab.weather.validate import (
    EPW_COLUMN_BOUNDS,
    assert_consecutive_hourly_index,
    assert_finite_in_bounds,
)

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
SOURCE_NAME = "open-meteo-archive"

# Open-Meteo hourly variable -> EPW-builder column (see wattlab/weather/epw.py)
COLUMN_MAP: dict[str, str] = {
    "temperature_2m": "dry_bulb_f",
    "dew_point_2m": "dew_point_f",
    "relative_humidity_2m": "relative_humidity_pct",
    "surface_pressure": "surface_pressure_hpa",
    "shortwave_radiation": "shortwave_radiation_wm2",
    "direct_normal_irradiance": "direct_normal_irradiance_wm2",
    "diffuse_radiation": "diffuse_radiation_wm2",
    "wind_speed_10m": "wind_speed_mph",
    "wind_direction_10m": "wind_direction_deg",
}

# Physical bounds keyed by Open-Meteo variable name (same numbers as EPW columns).
PHYSICAL_BOUNDS: dict[str, tuple[float, float]] = {
    variable: EPW_COLUMN_BOUNDS[column] for variable, column in COLUMN_MAP.items()
}

# Accepted unit strings for each variable when hourly_units is present.
# Open-Meteo commonly returns °F / % / hPa / W/m² / mp/h / °.
EXPECTED_HOURLY_UNITS: dict[str, frozenset[str]] = {
    "temperature_2m": frozenset({"°f", "f", "fahrenheit"}),
    "dew_point_2m": frozenset({"°f", "f", "fahrenheit"}),
    "relative_humidity_2m": frozenset({"%", "percent", "percentage"}),
    "surface_pressure": frozenset({"hpa"}),
    "shortwave_radiation": frozenset({"w/m²", "w/m2", "wm-2"}),
    "direct_normal_irradiance": frozenset({"w/m²", "w/m2", "wm-2"}),
    "diffuse_radiation": frozenset({"w/m²", "w/m2", "wm-2"}),
    "wind_speed_10m": frozenset({"mph", "mp/h", "mi/h"}),
    "wind_direction_10m": frozenset({"°", "deg", "degree", "degrees"}),
}

# Open-Meteo snaps requests to its model grid (~0.1 deg); allow that much drift.
COORD_TOLERANCE_DEG = 0.25

_MAX_BACKOFF_S = 60.0

Opener = Callable[[str], bytes]
SleepFn = Callable[[float], None]


def _default_opener(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as resp:
        return resp.read()


def build_archive_url(request: WeatherRequest) -> str:
    params = {
        "latitude": request.latitude,
        "longitude": request.longitude,
        "start_date": request.start_date.isoformat(),
        "end_date": request.end_date.isoformat(),
        "hourly": ",".join(request.variables),
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "timezone": "UTC",
    }
    return f"{ARCHIVE_URL}?{urlencode(params)}"


def _canonical_request(request: WeatherRequest) -> dict[str, Any]:
    return {
        "latitude": request.latitude,
        "longitude": request.longitude,
        "start_date": request.start_date.isoformat(),
        "end_date": request.end_date.isoformat(),
        "timezone": request.timezone,
        "variables": list(request.variables),
        "allow_partial": request.allow_partial,
    }


def _cache_path(request: WeatherRequest, cache_dir: Path) -> Path:
    key_src = json.dumps(
        {
            "source": SOURCE_NAME,
            "latitude": request.latitude,
            "longitude": request.longitude,
            "start_date": request.start_date.isoformat(),
            "end_date": request.end_date.isoformat(),
            "variables": sorted(request.variables),
            "allow_partial": request.allow_partial,
        },
        sort_keys=True,
    )
    key = hashlib.sha256(key_src.encode("utf-8")).hexdigest()[:20]
    return cache_dir / f"open_meteo_{key}.json"


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    fd, tmp_name = tempfile.mkstemp(
        dir=path.parent, prefix=".open_meteo_", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _normalize_unit(unit: str) -> str:
    return unit.strip().lower().replace(" ", "")


def _validate_hourly_units(payload: dict[str, Any]) -> None:
    units = payload.get("hourly_units")
    if units is None:
        return
    if not isinstance(units, dict):
        raise ValueError("hourly_units must be an object when present")
    for variable, accepted in EXPECTED_HOURLY_UNITS.items():
        if variable not in units:
            continue
        got = _normalize_unit(str(units[variable]))
        if got not in accepted:
            raise ValueError(
                f"hourly_units for {variable} must be one of "
                f"{sorted(accepted)} (got {units[variable]!r})"
            )


def _validate_coordinates(payload: dict[str, Any], request: WeatherRequest) -> None:
    for field in ("latitude", "longitude"):
        got = payload.get(field)
        want = getattr(request, field)
        if not isinstance(got, (int, float)) or abs(float(got) - want) > COORD_TOLERANCE_DEG:
            raise ValueError(
                f"response {field} {got!r} does not match requested "
                f"{field} {want} (tolerance {COORD_TOLERANCE_DEG} deg)"
            )


def _parse_timestamps(times: list[Any], request: WeatherRequest) -> pd.DatetimeIndex:
    if not times:
        raise ValueError("response hourly.time is empty")
    try:
        idx = pd.DatetimeIndex(pd.to_datetime(times, format="ISO8601", utc=True))
    except (ValueError, TypeError) as exc:
        raise ValueError(f"response hourly.time is not parseable: {exc}") from exc

    assert_consecutive_hourly_index(idx, context="response timestamps")

    expected_start = pd.Timestamp(request.start_date, tz="UTC")
    expected_end = pd.Timestamp(request.end_date, tz="UTC") + pd.Timedelta(hours=23)
    if idx[0] != expected_start or idx[-1] > expected_end:
        raise ValueError(
            f"response time span {idx[0]}..{idx[-1]} falls outside the "
            f"requested date range {request.start_date}..{request.end_date}"
        )
    return idx


def _validate_values(name: str, values: list[Any], n_rows: int) -> Any:
    if len(values) != n_rows:
        raise ValueError(
            f"hourly array length mismatch: {name} has {len(values)} values "
            f"but time has {n_rows}"
        )
    return assert_finite_in_bounds(name, values, PHYSICAL_BOUNDS[name])


def _payload_to_frame(payload: dict[str, Any], request: WeatherRequest) -> pd.DataFrame:
    """Validate an archive API payload and map it to EPW-builder columns."""
    if not isinstance(payload, dict):
        raise ValueError("response payload is not a JSON object")
    _validate_coordinates(payload, request)
    _validate_hourly_units(payload)

    hourly = payload.get("hourly")
    if not isinstance(hourly, dict) or "time" not in hourly:
        raise ValueError("response is missing the 'hourly' block with 'time'")

    missing = [v for v in COLUMN_MAP if v not in hourly]
    if missing:
        raise ValueError(
            "response is missing hourly variables: " + ", ".join(missing)
        )

    idx = _parse_timestamps(hourly["time"], request)
    data = {
        column: _validate_values(variable, hourly[variable], len(idx))
        for variable, column in COLUMN_MAP.items()
    }

    expected_rows = ((request.end_date - request.start_date).days + 1) * 24
    if len(idx) < expected_rows and not request.allow_partial:
        raise ValueError(
            f"incomplete coverage: got {len(idx)} of {expected_rows} expected "
            f"hourly rows for {request.start_date}..{request.end_date}; "
            "set WeatherRequest.allow_partial=True to accept a partial span"
        )

    df = pd.DataFrame(data, index=idx)
    df.index.name = "timestamp_utc"
    return df


def _request_matches(stored: dict[str, Any], request: WeatherRequest) -> bool:
    canonical = _canonical_request(request)
    try:
        return (
            float(stored["latitude"]) == canonical["latitude"]
            and float(stored["longitude"]) == canonical["longitude"]
            and stored["start_date"] == canonical["start_date"]
            and stored["end_date"] == canonical["end_date"]
            and stored["timezone"] == canonical["timezone"]
            and list(stored["variables"]) == canonical["variables"]
            and bool(stored.get("allow_partial", False)) == canonical["allow_partial"]
        )
    except (KeyError, TypeError, ValueError):
        return False


def _load_cache_envelope(
    raw: bytes, request: WeatherRequest
) -> tuple[pd.DataFrame, bytes, datetime] | None:
    """Return (df, response_body_bytes, downloaded_at) for a valid envelope."""
    try:
        envelope = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(envelope, dict):
        return None
    if "request" not in envelope or "response" not in envelope:
        return None  # legacy bare payload or corrupt wrapper
    if not _request_matches(envelope["request"], request):
        return None
    downloaded_raw = envelope.get("downloaded_at_utc")
    if not isinstance(downloaded_raw, str):
        return None
    try:
        downloaded_at = datetime.fromisoformat(downloaded_raw)
    except ValueError:
        return None
    if downloaded_at.tzinfo is None:
        downloaded_at = downloaded_at.replace(tzinfo=timezone.utc)

    wire = envelope.get("response_body")
    if isinstance(wire, str):
        response_bytes = wire.encode("utf-8")
    else:
        # Older/incomplete envelopes: fingerprint the re-serialized response.
        response_bytes = json.dumps(
            envelope["response"], separators=(",", ":"), sort_keys=True
        ).encode("utf-8")

    try:
        df = _payload_to_frame(envelope["response"], request)
    except (ValueError, KeyError, TypeError):
        return None
    return df, response_bytes, downloaded_at


def _is_retryable(exc: BaseException) -> bool:
    """Retry URLError / timeouts / HTTP 429 / HTTP 5xx only."""
    if isinstance(exc, TimeoutError):
        return True
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code == 429 or 500 <= exc.code <= 599
    if isinstance(exc, urllib.error.URLError):
        return True
    return False


def download_archive_weather(
    request: WeatherRequest,
    cache_dir: Path,
    opener: Opener | None = None,
    retries: int = 3,
    sleep: SleepFn | None = None,
) -> tuple[pd.DataFrame, WeatherDatasetMeta]:
    """Download (or reuse cached) hourly archive weather for `request`.

    Returns the validated hourly DataFrame (UTC index, EPW-builder columns)
    and a :class:`WeatherDatasetMeta` with sha256/provenance/cache details.
    Cache hits preserve the original ``downloaded_at_utc`` from the envelope.
    """
    if retries < 1:
        raise ValueError(f"retries must be >= 1 (got {retries})")
    if opener is None:
        opener = _default_opener
    if sleep is None:
        sleep = time.sleep

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = _cache_path(request, cache_dir)

    df: pd.DataFrame | None = None
    response_bytes: bytes | None = None
    downloaded_at: datetime | None = None

    if cache_path.exists():
        parsed = _load_cache_envelope(cache_path.read_bytes(), request)
        if parsed is not None:
            df, response_bytes, downloaded_at = parsed

    if df is None:
        url = build_archive_url(request)
        payload: dict[str, Any] | None = None
        last_exc: BaseException | None = None
        for attempt in range(retries):
            try:
                response_bytes = opener(url)
                payload = json.loads(response_bytes.decode("utf-8"))
                break
            except Exception as exc:
                if not _is_retryable(exc) or attempt >= retries - 1:
                    raise
                last_exc = exc
                sleep(min(2.0**attempt, _MAX_BACKOFF_S))
        else:
            assert last_exc is not None
            raise last_exc

        assert response_bytes is not None and payload is not None
        df = _payload_to_frame(payload, request)
        downloaded_at = datetime.now(timezone.utc)
        envelope = {
            "request": _canonical_request(request),
            "downloaded_at_utc": downloaded_at.isoformat(),
            "response": payload,
            # Original wire body so sha256 matches the network response.
            "response_body": response_bytes.decode("utf-8"),
        }
        _atomic_write_bytes(
            cache_path, json.dumps(envelope, ensure_ascii=False).encode("utf-8")
        )

    assert response_bytes is not None and downloaded_at is not None and df is not None
    meta = WeatherDatasetMeta(
        source=SOURCE_NAME,
        latitude=request.latitude,
        longitude=request.longitude,
        start_date=pd.Timestamp(df.index[0]).date(),
        end_date=pd.Timestamp(df.index[-1]).date(),
        timezone="UTC",
        variables=list(request.variables),
        rows=len(df),
        sha256=hashlib.sha256(response_bytes).hexdigest(),
        cached_path=str(cache_path),
        downloaded_at_utc=downloaded_at,
    )
    return df, meta
