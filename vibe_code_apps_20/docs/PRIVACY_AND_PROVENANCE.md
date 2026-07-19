# Privacy and provenance

WattLab public sources must remain client-neutral.

## Rules

- Never commit proprietary workbooks (`.xlsx` / `.xls` / `.xlsm`) or client trend exports.
- Never commit client, district, school, employee, or account identifiers.
- Calculator math is independently implemented HVAC engineering; private legacy workbooks are not runtime dependencies.
- Public wording uses: **Open, independently implemented HVAC bin-method screening calculators with synthetic golden tests.**

## Automated gate

```powershell
python -m wattlab.privacy.scan .
python -m pytest tests/test_no_proprietary_content.py -q
```

The deny-list is stored as SHA-256 hashes only (`wattlab/privacy/deny_list.py`). Literal proprietary search strings are not committed as searchable repository content.

## Internal audit

See [`privacy_and_provenance_audit.md`](privacy_and_provenance_audit.md) for categories inspected, remediation, history/image risk notes, and remaining concerns.

## Calculator provenance

Each ESCO-family calculator carries a provenance record in
`wattlab/data/bench/provenance.json` via `wattlab.bench.provenance`.
