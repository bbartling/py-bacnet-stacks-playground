# Agent CSV preprocess → multi-zip upload (human + Streamlit)

**Purpose:** Let a human upload a full building job through the Streamlit browser even when the assembled package is up to **~2 GB**, while each browser file stays under Streamlit’s **per-file** upload cap (**500 MB** in `.streamlit/config.toml`; some hosts still feel like ~200 MB — keep parts smaller if uploads fail).

This does **not** replace [`docs/PACKAGE_SPEC.md`](../../docs/PACKAGE_SPEC.md). It explains how agents **split** a valid `openfdd_package_v1` tree into multiple zips the UI can merge.

---

## End-to-end flow

```text
Historian CSVs (site)
        │
        ▼
Agent preprocess (pandas) ──► openfdd_package_v1 tree
        │
        ├─ optional: column_map.json / session_config.json
        │
        ▼
Split into part zips (each ≤ browser cap)
        │
        ▼
Human: Streamlit sidebar → select ALL part zips → Load zip(s)
        │
        ▼
App merges parts → data-contract warnings → session frames
        │
        ▼
Human or agent: Map + prerun all faults
        │
        ▼
Human: Plots (validation cards / FDD DOCX) / RCx / Analytics / download session config
```

---

## Part zip rules

1. **Each part** is a normal zip of package paths (same layout as PACKAGE_SPEC).
2. **`manifest.json` must appear in exactly one part** (usually `part01` or a tiny `manifest` zip).
3. Equipment folders may be split across parts (`AHU_*` in part01, `VAV/*` in part02, …).
4. Shared `weather/` may live in any one part (do not duplicate conflicting weather files).
5. Optional root `job_manifest.json`:

```json
{
  "schema_version": "openfdd_job_v1",
  "building_id": "BUILDING_100",
  "parts": [
    "BUILDING_100_part01.zip",
    "BUILDING_100_part02.zip",
    "BUILDING_100_part03.zip"
  ],
  "notes": "Split for Streamlit multi-upload"
}
```

6. Prefer names that sort naturally: `*_part01.zip`, `*_part02.zip`, …
7. **Do not invent** history rows or trusted quality windows to “fix” gaps — surface warnings instead.

### Suggested split strategies (pandas)

| Strategy | When |
| --- | --- |
| By equipment folder | Many AHU/VAV folders; zip until approaching ~400 MB |
| By time shard | Rare — prefer equipment split; time shards need identical columns |
| Manifest-only first zip | Tiny zip with `manifest.json` + `session_config.json` + `column_map.json` |

Pseudo:

```python
# Pseudocode — agent local script
# 1) Build full package dir per PACKAGE_SPEC
# 2) Walk equipment folders; pack into part zips while size < 400_000_000
# 3) Put manifest.json (+ optional maps) in part01
# 4) Hand part zips to human for Streamlit multi-upload
```

---

## After upload (agent / human)

In the Streamlit sidebar:

1. **Load zip(s)** — merges parts (`app/multi_zip.py`).
2. **Map + prerun all faults** — auto-builds column map if missing, runs all active rules into `batch_results`.
3. Human opens **Plots** (rule cards + Download FDD DOCX) / **RCx** / **Analytics**. Errors stay explicit (`ERROR` / `SKIPPED_*` / `NOT_APPLICABLE_*`).

Headless equivalent (path load, no browser cap):

```bash
python scripts/agent_afdd.py --package /path/to/full_or_merged.zip --out out_job --run-all
```

---

## Size cheat sheet

| Limit | Value | Where |
| --- | --- | --- |
| Per browser file | **500 MB** (config) | `.streamlit/config.toml` `maxUploadSize` |
| Assembled job | **2048 MB** default | `package_io.DEFAULT_PACKAGE_MB` |
| Path / CLI / Docker mount | same 2048 MB | bypasses multi-upload |

If a single equipment CSV alone exceeds the browser cap, use **Load zip from path** / Docker `/data` mount / `agent_afdd` — multi-upload cannot split one file mid-CSV in the browser.

---

## Related

- [`docs/PACKAGE_SPEC.md`](../../docs/PACKAGE_SPEC.md)
- [`DATA_CONTRACT.md`](../DATA_CONTRACT.md)
- [`docs/DOCKER.md`](../../docs/DOCKER.md)
- [`AGENTS.md`](../../AGENTS.md)
