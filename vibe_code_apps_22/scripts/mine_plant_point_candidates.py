#!/usr/bin/env python
"""Mine plant-point candidates from site FDD / Haystack exports — never invent BACnet IDs.

Writes docs/audits/plant_point_candidates.md (+ optional CSV under reports/ml/).
Exit 0 even when nothing found (documents NOT_IN_HISTORIAN).
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(_APP), str(_APP / "scripts")]

ROLES: dict[str, tuple[str, ...]] = {
    "hp_enable_or_stage": (
        "hp stage",
        "hp enable",
        "heat pump",
        "compressor stage",
        "hp_on",
        "wshp",
    ),
    "fan_status": ("fan status", "fan on", "supply fan", "fan cmd", "fan_status"),
    "sat_rat": ("supply air temp", "return air temp", "sat", "rat", "sa temp", "ra temp"),
    "loop_ewt": ("entering water", "ewt", "source ewt", "loop ewt", "condenser ewt"),
    "loop_lwt": ("leaving water", "lwt", "source lwt", "loop lwt"),
    "pump_speed_or_kw": ("pump speed", "pump kw", "pump power", "gpm", "loop pump", "flow"),
    "doas_or_oa_signal": ("doas", "oa damper", "outdoor air", "oa cmd", "fresh air"),
}


def _site() -> Path:
    for k in ("LAKESIDE_SITE_ROOT", "VIBE22_SITE_ROOT"):
        v = os.environ.get(k, "").strip()
        if v and Path(v).is_dir():
            return Path(v)
    raise SystemExit("LAKESIDE_SITE_ROOT (or VIBE22_SITE_ROOT) required")


def _candidate_files(site: Path) -> list[Path]:
    cands: list[Path] = []
    named = [
        site / "fdd_device_lookup.csv",
        site / "reports" / "fdd_export.csv",
        site / "haystack" / "points.csv",
        site / "haystack" / "point_map.csv",
        site / "maps" / "haystack_points.csv",
        site / "bacnet" / "point_map.csv",
    ]
    for p in named:
        if p.is_file():
            cands.append(p)
    for dname in ("haystack", "maps", "bacnet", "fdd", "openfdd"):
        d = site / dname
        if d.is_dir():
            cands.extend(sorted(d.glob("*.csv")))
    # de-dupe
    seen: set[Path] = set()
    out: list[Path] = []
    for p in cands:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            out.append(p)
    return out


def _strings_from_csv(path: Path) -> list[tuple[str, str]]:
    """Return (column, cell_or_header) pairs for fuzzy ranking."""
    import pandas as pd

    rows: list[tuple[str, str]] = []
    try:
        df = pd.read_csv(path, nrows=2000)
    except Exception:
        return rows
    for c in df.columns:
        rows.append(("__header__", str(c)))
    for c in df.columns:
        series = df[c].dropna().astype(str).head(500)
        for v in series:
            s = v.strip()
            if s and s.lower() not in {"nan", "none"}:
                rows.append((str(c), s))
    return rows


def score_match(text: str, needles: tuple[str, ...]) -> float:
    t = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    if not t:
        return 0.0
    best = 0.0
    for n in needles:
        n2 = n.lower()
        if n2 == t:
            best = max(best, 1.0)
        elif n2 in t or t in n2:
            best = max(best, 0.75)
        else:
            # token overlap
            ta, tb = set(t.split()), set(n2.split())
            if ta and tb:
                best = max(best, len(ta & tb) / len(ta | tb))
    return best


def mine(site: Path) -> list[dict[str, str]]:
    files = _candidate_files(site)
    hits: list[dict[str, str]] = []
    if not files:
        for role in ROLES:
            hits.append(
                {
                    "role": role,
                    "status": "NOT_IN_HISTORIAN",
                    "raw_name": "",
                    "source_path": "NONE",
                    "source_column": "",
                    "score": "0",
                    "note": "No FDD/Haystack/bacnet CSV maps found under site",
                }
            )
        return hits

    corpus: list[tuple[str, str, str]] = []  # path, column, text
    for p in files:
        for col, text in _strings_from_csv(p):
            corpus.append((str(p), col, text))

    for role, needles in ROLES.items():
        ranked: list[tuple[float, str, str, str]] = []
        for path, col, text in corpus:
            sc = score_match(text, needles)
            if sc >= 0.5:
                ranked.append((sc, path, col, text))
        ranked.sort(key=lambda x: -x[0])
        if not ranked:
            hits.append(
                {
                    "role": role,
                    "status": "NOT_IN_HISTORIAN",
                    "raw_name": "",
                    "source_path": ";".join(str(f) for f in files[:5]),
                    "source_column": "",
                    "score": "0",
                    "note": "Scanned site maps; no fuzzy match ≥0.5 — do not invent BACnet IDs",
                }
            )
        else:
            sc, path, col, text = ranked[0]
            hits.append(
                {
                    "role": role,
                    "status": "CANDIDATE",
                    "raw_name": text[:200],
                    "source_path": path,
                    "source_column": col,
                    "score": f"{sc:.2f}",
                    "note": "Candidate only — confirm before adding to 15-min export / inventory PRESENT",
                }
            )
            # extras
            for sc, path, col, text in ranked[1:3]:
                hits.append(
                    {
                        "role": role,
                        "status": "CANDIDATE_ALT",
                        "raw_name": text[:200],
                        "source_path": path,
                        "source_column": col,
                        "score": f"{sc:.2f}",
                        "note": "Alternate candidate",
                    }
                )
    return hits


def write_md(path: Path, rows: list[dict[str, str]], site: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    n_cand = sum(1 for r in rows if r["status"] == "CANDIDATE")
    n_miss = sum(1 for r in rows if r["status"] == "NOT_IN_HISTORIAN")
    lines = [
        "# Plant point candidates (sensor archaeology)",
        "",
        f"**Site:** `{site}`",
        f"**Primary candidates:** {n_cand} · **NOT_IN_HISTORIAN roles:** {n_miss}",
        "",
        "Honesty: raw names from site FDD/Haystack CSVs only. "
        "**No BACnet object IDs invented.** Candidates are not PRESENT until "
        "confirmed in the 15-min export / inventory.",
        "",
        "| Role | Status | Score | Raw name | Source |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        if r["status"] == "CANDIDATE_ALT":
            continue
        lines.append(
            f"| `{r['role']}` | {r['status']} | {r['score']} | "
            f"`{r['raw_name'][:60]}` | `{Path(r['source_path']).name if r['source_path'] else ''}` |"
        )
    lines.append("")
    lines.append("See also `reports/ml/plant_point_candidates.csv`.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys()) if rows else []
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--site", type=Path, default=None)
    ap.add_argument(
        "--md-out",
        type=Path,
        default=_APP / "docs" / "audits" / "plant_point_candidates.md",
    )
    ap.add_argument(
        "--csv-out",
        type=Path,
        default=_APP / "reports" / "ml" / "plant_point_candidates.csv",
    )
    args = ap.parse_args(argv)
    site = args.site or _site()
    rows = mine(site)
    write_csv(args.csv_out, rows)
    write_md(args.md_out, rows, site)
    n_cand = sum(1 for r in rows if r["status"] == "CANDIDATE")
    print(f"wrote {args.md_out} candidates={n_cand} site={site}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
