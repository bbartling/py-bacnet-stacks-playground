import { describe, expect, it } from "vitest";
import { formatRuleTestEvents } from "./rule-lab-console";

describe("formatRuleTestEvents", () => {
  it("formats stdout instead of [object Object]", () => {
    const text = formatRuleTestEvents([
      { type: "stdout", text: "--- sweeping 120 rows ---\n" },
      { type: "stdout", text: "2024-01-01  OOB avg  72.00 °F\n" },
      { type: "row", row: 1, ts: "t", status: "ok", degF: 70 },
      { type: "summary", rows: 120, flagged: 0, sweep_mode: "per_row" },
    ]);
    expect(text).toContain("sweeping 120 rows");
    expect(text).toContain("OOB avg");
    expect(text).not.toContain("[object Object]");
  });
});
