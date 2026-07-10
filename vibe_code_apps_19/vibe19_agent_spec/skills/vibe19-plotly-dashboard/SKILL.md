---
name: vibe19-plotly-dashboard
description: >-
  Use for Plotly charts inside the Streamlit demo (not static HTML FastAPI pages).
  Triggers on: Plotly, chart, trends, fault chart, Streamlit figure.
---

# Vibe19 — Plotly charts (Streamlit)

Charts live in the Streamlit app via `app/charts.py` and `st.plotly_chart`.

**Do not** rebuild the old static HTML / FastAPI dashboard pages.

## Key files

| File | Role |
| --- | --- |
| `app/charts.py` | Rule result / trend figures |
| `streamlit_app.py` | Renders charts in tabs |

## Pattern

```python
import streamlit as st
from app.charts import rule_result_chart

fig = rule_result_chart(df, result)
st.plotly_chart(fig, use_container_width=True)
```

→ Full app skill: [`vibe19-streamlit-demo/SKILL.md`](../vibe19-streamlit-demo/SKILL.md)
