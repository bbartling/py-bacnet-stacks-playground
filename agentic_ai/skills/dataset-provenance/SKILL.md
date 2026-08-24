---
name: dataset-provenance
description: Acquire and retain public building datasets reproducibly, with source hashes, safe extraction, and a strict raw-versus-derived boundary.
---

# Public dataset provenance

## Goal
Acquire public building datasets reproducibly without committing huge archives or losing source provenance.

## Procedure
1. Record canonical landing page, DOI, release/version date, publisher and license.
2. Prefer a publisher API or stable archive endpoint over scraping.
3. Download to ignored `data/raw/` using a `.part` file and atomic rename.
4. Reject ZIP members that resolve outside the destination directory.
5. SHA-256 hash source archives and important extracted metadata.
6. Write a machine-readable acquisition manifest with URL, DOI, bytes, hash and timestamp.
7. Keep raw source files immutable. Derived tables belong in `data/processed/` with their own provenance.
8. Never commit multi-GB telemetry for convenience.

## Failure posture
Unexpected package layout, hash mismatch, ambiguous release or unsafe archive paths fail closed. Never silently swap in another dataset release.
