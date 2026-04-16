export function cn(...parts: Array<string | false | undefined | null>): string {
  return parts.filter(Boolean).join(" ");
}

export function prettyJson(v: unknown): string {
  return JSON.stringify(v, null, 2);
}
