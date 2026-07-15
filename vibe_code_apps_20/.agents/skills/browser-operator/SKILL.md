# Sketchbox Browser Operator

## Purpose
Execute approved model actions safely through Playwright.

## Invoke when
Login, navigation, input changes, saves, exports, or runs.

## Required inputs
- Approved action plan
- current UI map
- credentials via environment
- recovery export path

## Procedure
1. Probe.
2. Authenticate.
3. Verify project.
4. Capture pre-state.
5. Perform one semantic action.
6. Read back.
7. Capture post-state.
8. Write event log.

## Outputs
- action log
- screenshots
- DOM/state summaries
- downloads

## Guardrails
Never log credentials. Never continue after selector ambiguity or unexpected modal.
Prefer helpers in `sketchbox_ui.py` (`goto_view`, `select_by_label`, `write_and_read_back`) and keep `SELECTOR_MAP_VERSION` in sync when selectors change.

## Validation
Browser-write checklist passes for every mutation.
