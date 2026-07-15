"""Shared Sketchbox UI helpers — single place for verified selectors."""

from __future__ import annotations

from playwright.sync_api import Page

# Verified live facts (2026-07). Update when UI changes; bump SELECTOR_MAP_VERSION.
SELECTOR_MAP_VERSION = "2026-07-15"


def goto_view(page: Page, view: str) -> None:
    """Tabs are ``div.view-link[view=project|schedules|measures|results]`` (lowercase)."""
    key = view.strip().lower()
    loc = page.locator(f'div.view-link[view="{key}"]').first
    if loc.count():
        loc.click(timeout=8000)
    else:
        page.evaluate(
            """(view) => {
          const el = document.querySelector(`div.view-link[view="${view}"]`);
          if (el) el.click();
        }""",
            key,
        )
    page.wait_for_timeout(1000)


def select_by_label(page: Page, label: str, option_text: str, timeout_ms: int = 4000) -> dict:
    info: dict = {"label": label, "option": option_text, "ok": False}
    try:
        lab = page.locator(f"label:text-is('{label}')").first
        if lab.count() == 0:
            info["error"] = "label_missing"
            return info
        sel = lab.locator(
            "xpath=ancestor::div[contains(@class,'ripple-input')][1]//select"
        ).first
        if sel.count() == 0:
            info["error"] = "select_missing"
            return info
        if sel.get_attribute("disabled") is not None:
            info["error"] = "select_disabled"
            return info
        sel.select_option(value=option_text, timeout=timeout_ms)
        page.wait_for_timeout(300)
        info["ok"] = True
        info["observed"] = sel.input_value()
        return info
    except Exception as exc:
        info["error"] = str(exc)[:240]
        return info


def write_and_read_back(page: Page, locator_css: str, value: str) -> dict:
    """Fill a text input and record the *observed* value after Tab."""
    out: dict = {"selector": locator_css, "intended": value, "ok": False}
    el = page.locator(locator_css).first
    try:
        if el.count() == 0:
            out["error"] = "missing"
            return out
        out["before"] = el.input_value()
        el.fill(value, timeout=4000)
        el.press("Tab")
        page.wait_for_timeout(200)
        observed = el.input_value()
        out["observed"] = observed
        out["ok"] = observed == value or observed == str(int(float(value)))
        return out
    except Exception as exc:
        out["error"] = str(exc)[:240]
        return out


COOLING_OFFSET_CSS = 'input[type="text"][title*="cooling setpoint by this offset"]'
HEATING_OFFSET_CSS = 'input[type="text"][title*="heating setpoint by this offset"]'
