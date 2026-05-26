/** Format playground test-rule events for the Rule Lab console and LLM copy bundle. */

export type RuleTestEvent = {
  type?: string;
  text?: string;
  row?: number;
  ts?: string;
  status?: string;
  degF?: number;
  message?: string;
  rows?: number;
  flagged?: number;
  raw_tripped?: number;
  sweep_mode?: string;
};

export function formatRuleTestEvents(events: RuleTestEvent[], opts?: { maxLines?: number }): string {
  const max = opts?.maxLines ?? 200;
  const lines: string[] = [];
  let n = 0;

  const push = (line: string) => {
    if (n >= max) return;
    lines.push(line);
    n += 1;
  };

  for (const evt of events) {
    if (n >= max) break;
    const t = evt.type || "";
    if (t === "stdout" || t === "error") {
      const text = (evt.text || "").replace(/\r\n/g, "\n");
      for (const part of text.split("\n")) {
        if (part.trim() || text.includes("\n")) push(part);
      }
      continue;
    }
    if (t === "row") {
      if (evt.status === "fault" || evt.status === "error") {
        const temp =
          evt.degF != null && Number.isFinite(evt.degF) ? `  ${Number(evt.degF).toFixed(2)} °F` : "";
        const msg = evt.status === "error" ? ` ERROR ${evt.message || ""}` : " FAULT";
        push(`row ${evt.row ?? "?"}  ${evt.ts ?? ""}${temp}${msg}`);
      }
      continue;
    }
    if (t === "summary") {
      push(
        `--- sweep: ${evt.flagged ?? 0} flagged / ${evt.rows ?? 0} rows (mode=${evt.sweep_mode || "?"}) ---`,
      );
    }
  }

  if (events.length > max) {
    lines.push(`… (${events.length - max} more events omitted)`);
  }
  return lines.join("\n");
}

export function buildRuleLabLlmBundle(args: {
  siteId: string;
  buildingId: string;
  rule: { id?: string; title?: string; code?: string; config?: Record<string, unknown>; brick_scope?: Record<string, unknown> };
  testSummary: string;
  consoleBody: string;
  brickScopeNote?: string;
}): string {
  const { siteId, buildingId, rule, testSummary, consoleBody, brickScopeNote } = args;
  const parts = [
    "# Vibe12 Rule Lab — copy for external LLM",
    "",
    `Site: ${siteId} / ${buildingId}`,
    `Rule: ${rule.title || rule.id || "?"}`,
    "",
    "## Test summary",
    testSummary,
    "",
  ];
  if (brickScopeNote) {
    parts.push("## BRICK scope (production targets)", brickScopeNote, "");
  }
  parts.push(
    "## Config (JSON)",
    "```json",
    JSON.stringify(rule.config || {}, null, 2),
    "```",
    "",
    "## Python evaluate()",
    "```python",
    rule.code || "",
    "```",
    "",
    "## Console / print output",
    consoleBody || "(no output)",
    "",
  );
  return parts.join("\n");
}

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

export function downloadJson(filename: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
