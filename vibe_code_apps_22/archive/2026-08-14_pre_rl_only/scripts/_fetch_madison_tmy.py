"""One-shot: download Madison WI TMY EPW into SITE_ROOT/eplus/weather."""
from __future__ import annotations

import io
import re
import sys
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

DEST = Path(r"C:\Users\ben\OneDrive\Desktop\testing\sp_creekside\eplus\weather")
OUT_NAME = "USA_WI_Madison-Dane.County.AP.726410_TMY3.epw"
UA = "Mozilla/5.0 (compatible; vibe22-weather-fetch/1.0)"

CANDIDATE_URLS = [
    # climate.onebuilding (current layout under USA_United_States_of_America/WI_Wisconsin)
    "https://climate.onebuilding.org/WMO_Region_4_North_and_Central_America/USA_United_States_of_America/WI_Wisconsin/USA_WI_Madison-Dane.County.Rgnl.AP-Truax.Field.726410_TMY3.zip",
    "https://climate.onebuilding.org/WMO_Region_4_North_and_Central_America/USA_United_States_of_America/WI_Wisconsin/USA_WI_Madison-Dane.County.Rgnl.AP-Truax.Field.726410_TMYx.zip",
]


def _get(url: str, timeout: int = 60) -> tuple[int, bytes]:
    req = Request(url, headers={"User-Agent": UA})
    try:
        with urlopen(req, timeout=timeout) as resp:
            return int(getattr(resp, "status", 200) or 200), resp.read()
    except Exception as exc:  # noqa: BLE001
        code = getattr(getattr(exc, "code", None), "real", None) or getattr(exc, "code", None)
        return int(code or 0), str(exc).encode("utf-8", errors="ignore")


def _extract_epw(blob: bytes) -> bytes | None:
    if blob[:10].startswith(b"LOCATION,"):
        return blob
    try:
        zf = zipfile.ZipFile(io.BytesIO(blob))
    except zipfile.BadZipFile:
        return None
    for name in zf.namelist():
        if name.lower().endswith(".epw") and "madison" in name.lower():
            return zf.read(name)
    for name in zf.namelist():
        if name.lower().endswith(".epw"):
            return zf.read(name)
    return None


def _discover_from_region4() -> list[str]:
    urls: list[str] = []
    status, body = _get(
        "https://climate.onebuilding.org/WMO_Region_4_North_and_Central_America/default.html"
    )
    if status != 200:
        return urls
    text = body.decode("utf-8", errors="ignore")
    hrefs = re.findall(r'href="([^"]+)"', text)
    base = "https://climate.onebuilding.org/WMO_Region_4_North_and_Central_America/"
    wi_pages = []
    for h in hrefs:
        if "USA_WI" in h or "Wisconsin" in h:
            wi_pages.append(h if h.startswith("http") else base + h.lstrip("./"))
    # also try direct country folder listing patterns
    wi_pages.extend(
        [
            base + "USA_WI/default.html",
            base + "USA_WI.html",
            base + "USA/WI/default.html",
        ]
    )
    for page in wi_pages:
        st, html = _get(page)
        print(f"page {st} {page}")
        if st != 200:
            continue
        page_text = html.decode("utf-8", errors="ignore")
        for h in re.findall(r'href="([^"]+\.zip)"', page_text):
            if "Madison" not in h and "726410" not in h:
                continue
            url = h if h.startswith("http") else str(Path(page).parent).replace("\\", "/") + "/" + h
            # Path parent of URL is messy; join properly
            if not h.startswith("http"):
                root = page.rsplit("/", 1)[0] + "/"
                url = root + h.lstrip("./")
            urls.append(url)
        # bare mentions
        for m in re.findall(r'[\w./-]*Madison[\w./-]*726410[\w./-]*\.zip', page_text):
            if m.startswith("http"):
                urls.append(m)
            else:
                root = page.rsplit("/", 1)[0] + "/"
                urls.append(root + m.lstrip("./"))
    return list(dict.fromkeys(urls))


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    tried = list(dict.fromkeys(CANDIDATE_URLS + _discover_from_region4()))
    print(f"candidates={len(tried)}")
    for url in tried:
        st, blob = _get(url)
        print(f"try {st} {len(blob)} {url}")
        if st != 200 or len(blob) < 50_000:
            continue
        epw = _extract_epw(blob)
        if not epw or not epw.lstrip().startswith(b"LOCATION"):
            print("  not an EPW/zip-with-EPW")
            continue
        out = DEST / OUT_NAME
        out.write_bytes(epw)
        print(f"WROTE {out} ({out.stat().st_size} bytes)")
        # verify classifier
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from eplus_gym_app.weather_files import classify_epw, weather_inventory

        site = DEST.parents[1]
        inv = weather_inventory(site)
        print("classify", classify_epw(out))
        print("inventory_tmy", inv.get("tmy"))
        print("default_mode", inv.get("default_mode"))
        print("note", inv.get("tmy_missing_note"))
        return 0
    print("FAILED: no Madison TMY URL worked", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
