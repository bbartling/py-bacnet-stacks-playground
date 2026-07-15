# UI Change Recovery

1. Stop writes immediately.
2. Capture screenshot, URL, page title, accessible labels, and a redacted DOM excerpt.
3. Mark run `BLOCKED_UI_CHANGE`.
4. Compare against the last UI fingerprint.
5. Update exploration mappings before action mappings.
6. Add or update a contract fixture.
7. Re-run read-only probe.
8. Require review before resuming writes.
