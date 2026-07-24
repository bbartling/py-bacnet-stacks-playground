#!/usr/bin/env python3
import pandas as pd
from pathlib import Path

p = Path("/data/.artifacts/geo_b100_6fl_glass/dump_b100/telemetry")
print("files", sorted(f.name for f in p.iterdir())[:30])
f = p / "BOILERS_PUMPS.csv"
df = pd.read_csv(f)
print("cols", list(df.columns))
for c in df.columns:
    if any(x in c.lower() for x in ["hws", "hwr", "hot", "outside", "oat", "boiler"]):
        s = pd.to_numeric(df[c], errors="coerce").dropna()
        print(
            f"  {c}: n={len(s)} mean={s.mean():.1f} med={s.median():.1f} "
            f"p10={s.quantile(0.1):.1f} p90={s.quantile(0.9):.1f}"
        )

hws = "hot-water-supply-temp"
oat = "outside-air-temp"
d = df[[hws, oat]].apply(pd.to_numeric, errors="coerce").dropna()
d = d[d[hws] > 100]
d["bin"] = (d[oat] // 5) * 5
g = d.groupby("bin")[hws].agg(["median", "count"])
print(g.to_string())
print("OAT<30 HWS", float(d[d[oat] < 30][hws].median()))
print("OAT 30-50 HWS", float(d[(d[oat] >= 30) & (d[oat] < 50)][hws].median()))
print("OAT>50 HWS", float(d[d[oat] > 50][hws].median()))
