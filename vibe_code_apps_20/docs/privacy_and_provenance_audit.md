# Privacy and provenance audit

Date: 2026-07-19

## Scope and search categories

The audit covers client and district identifiers, individual facility names,
workbook authors and email addresses, source filenames and paths, BAS labels
that could identify a site, copied workbook comments or formulas, external
workbook links, extracted workbook XML, and legacy wording that implies a
direct source-code port.

Literal deny-list terms are stored only as normalized SHA-256 hashes in
`wattlab/privacy/deny_list.py`. Scanner output reports hashes and locations,
not the underlying terms.

## Locations inspected

- WattLab Python, JSON, YAML, TOML, Markdown, CSV, HTML, text, SQL, and notebook
  files under `vibe_code_apps_20`
- Tests, examples, agent instructions, skills, and session documentation
- Package data and calculator provenance records
- The tree for prohibited `.xlsx`, `.xls`, and `.xlsm` files

Generated environments, caches, artifacts, dependency trees, and Git internals
are excluded from the working-tree scan.

## Findings and remediation

The working tree contained legacy language describing direct workbook lineage
and generic labels that still tied tests to private source material. Public
wording now describes open, independently implemented HVAC bin-method screening
calculators with synthetic golden tests. Calculator math was not changed.

No source workbook is retained. Automated tests fail on a hash-only deny-list
match or a prohibited workbook binary. Read-only XLSX inspection helpers are
available for private audit use and report external-link parts and core
document properties without making a workbook a runtime dependency.

Each public calculator has a packaged clean-room provenance record. The records
state the engineering basis, private numerical validation status, and absence
of a workbook runtime dependency.

## Remaining concerns

The scanner can only detect terms represented in its hash set. Add newly
discovered restricted identifiers as normalized hashes, never plaintext.
Human review remains necessary for transformed identifiers, screenshots,
images, archives, and semantic leakage that exact n-gram hashing cannot detect.

Notebook output and future generated fixtures should receive both automated
and manual review. Private audit inputs must remain outside the repository.

## Git history

This audit validates the current working tree, not every unreachable local Git
object or third-party clone. Earlier history was previously rewritten during a
name scrub, but maintainers should separately verify remote refs and retained
backups before making an absolute historical-erasure claim.

## Docker images

Working-tree cleanup does not remove content from already-built image layers or
registry caches. Rebuild public images from the clean commit without build
cache, publish new immutable digests, inspect the resulting filesystem, and
retire superseded tags according to registry retention policy.
