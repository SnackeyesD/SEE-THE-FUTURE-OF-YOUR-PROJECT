function collectNumbers(value: unknown, target: Set<number>): void {
  if (typeof value === "number" && Number.isFinite(value)) {
    target.add(value);
    target.add(Math.abs(value));
    target.add(value * 100);
    target.add(value / 100);
    return;
  }
  if (Array.isArray(value)) {
    for (const item of value) collectNumbers(item, target);
    return;
  }
  if (value && typeof value === "object") {
    for (const item of Object.values(value)) collectNumbers(item, target);
  }
}

const NUMBER_PATTERN = /\d[\d\s\u00a0\u202f.,]*/g;

function normalizeToken(raw: string): string | null {
  const trimmed = raw.replace(/[\s\u00a0\u202f]+/g, "").replace(/[.,]+$/g, "");
  if (!trimmed) return null;
  if (trimmed.includes(",") && trimmed.includes(".")) {
    return trimmed.replace(/\./g, "").replace(",", ".");
  }
  return trimmed.replace(",", ".");
}

export function verifyNarration(text: string, result: unknown): string[] {
  const allowed = new Set<number>();
  collectNumbers(result, allowed);
  const cleaned = text.replace(/P(10|50|90)/gi, "P");
  const unknown: string[] = [];
  for (const match of cleaned.matchAll(NUMBER_PATTERN)) {
    const raw = match[0];
    const token = normalizeToken(raw);
    if (token === null) continue;
    const parsed = Number(token);
    if (!Number.isFinite(parsed)) continue;
    if (!allowed.has(parsed) && !allowed.has(Math.round(parsed))) {
      unknown.push(raw.trim());
    }
  }
  return [...new Set(unknown)];
}
