"""Upload parsers for IDF, EnergyPlus EPW, and tariff CSV (Pydantic)."""
from __future__ import annotations

import csv
import io
from pathlib import Path

from .models import OutdoorDay, TariffUpload

_EPW_LOCATION_RE_PREFIX = "LOCATION"


def parse_epw_day(
    text: str,
    *,
    month: int,
    day: int,
    source_name: str = "weather.epw",
) -> OutdoorDay:
    """Extract 24 hourly dry-bulb values for one calendar day from EPW text.

    EPW data columns: year, month, day, hour (1-24), minute, datasource, dry-bulb °C.
    """
    location = None
    by_hour: dict[int, float] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.upper().startswith("LOCATION"):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) > 1:
                location = ", ".join(x for x in parts[1:4] if x)
            continue
        if line[0].isalpha():
            continue
        parts = line.split(",")
        if len(parts) < 7:
            continue
        try:
            mo, dy, hr = int(float(parts[1])), int(float(parts[2])), int(float(parts[3]))
            dbc = float(parts[6])
        except ValueError:
            continue
        if mo == month and dy == day and 1 <= hr <= 24:
            by_hour[hr] = dbc
    if len(by_hour) < 24:
        raise ValueError(f"EPW missing hourly dry-bulb for {month:02d}/{day:02d} (got {len(by_hour)} hours)")
    drybulb_c = [by_hour[h] for h in range(1, 25)]
    drybulb_f = [round(c * 9.0 / 5.0 + 32.0, 2) for c in drybulb_c]
    return OutdoorDay(
        source_name=source_name,
        month=month,
        day=day,
        drybulb_c=drybulb_c,
        drybulb_f=drybulb_f,
        location=location,
    )


def parse_epw_path(path: Path | str, *, month: int, day: int) -> OutdoorDay:
    p = Path(path)
    return parse_epw_day(p.read_text(encoding="utf-8", errors="replace"), month=month, day=day, source_name=p.name)


def parse_tariff_csv(text: str, *, source_name: str = "tariff.csv") -> TariffUpload:
    """Accept 24/96/288 rates as a single column, or hour,rate / interval,rate headers."""
    sample = text.lstrip("\ufeff")
    reader = csv.reader(io.StringIO(sample))
    rows = [r for r in reader if any(c.strip() for c in r)]
    if not rows:
        raise ValueError("empty tariff CSV")
    header = [c.strip().lower() for c in rows[0]]
    rates: list[float] = []
    if any("rate" in h or "usd" in h or "price" in h for h in header) and len(header) >= 2:
        rate_idx = next((i for i, h in enumerate(header) if "rate" in h or "usd" in h or "price" in h), 1)
        for row in rows[1:]:
            if len(row) <= rate_idx:
                continue
            rates.append(float(row[rate_idx]))
    else:
        start = 1 if header and header[0].isalpha() else 0
        for row in rows[start:]:
            token = row[-1].strip() if row else ""
            if not token:
                continue
            rates.append(float(token))
    n = len(rates)
    return TariffUpload(source_name=source_name, intervals=n, rates_usd_per_kwh=rates)


def expand_tariff_to_288(upload: TariffUpload) -> list[float]:
    rates = list(upload.rates_usd_per_kwh)
    if len(rates) == 288:
        return rates
    if len(rates) == 24:
        return [r for r in rates for _ in range(12)]
    if len(rates) == 96:
        return [r for r in rates for _ in range(3)]
    raise ValueError("unsupported tariff interval count")
