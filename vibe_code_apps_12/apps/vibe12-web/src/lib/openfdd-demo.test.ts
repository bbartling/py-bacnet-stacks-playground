import { describe, expect, it } from "vitest";
import { ARROW_RULE_CONTRACT, DEMO_HERO_TITLE } from "./openfdd-demo";

describe("openfdd demo copy", () => {
  it("documents Arrow rule contract for Rule Lab", () => {
    expect(ARROW_RULE_CONTRACT).toContain("apply_faults_arrow");
    expect(ARROW_RULE_CONTRACT).not.toContain("evaluate(row");
  });

  it("uses Open-FDD cloud demo branding", () => {
    expect(DEMO_HERO_TITLE).toMatch(/Open-FDD/);
  });
});
