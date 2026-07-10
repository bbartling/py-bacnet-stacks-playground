---
name: vibe19-haystack-rdf
description: >-
  RETIRED RDF/Oxigraph. For Haystack-like column map names (siteRef, equip, device,
  points) use vibe19-streamlit-demo + docs/HAYSTACK_LIKE_MAPPING_GUIDE.md.
  Triggers on: Haystack RDF, Oxigraph, SPARQL, data_model.html.
---

# RETIRED — Haystack RDF / Oxigraph

**Do not re-add RDF, SPARQL, or Oxigraph to App 19.**

## What *is* supported (no RDF)

Haystack-**like** authoring names for column maps:

- `siteRef`, `equip`, `device`, `equipType`, `points`
- Point names like `discharge-air-temp`, `zone-air-temp`

Implemented in `app/column_map_json.py` → cookbook roles for rules.

→ **[`vibe19-streamlit-demo/SKILL.md`](../vibe19-streamlit-demo/SKILL.md)**  
→ **[`docs/HAYSTACK_LIKE_MAPPING_GUIDE.md`](../../../docs/HAYSTACK_LIKE_MAPPING_GUIDE.md)**
