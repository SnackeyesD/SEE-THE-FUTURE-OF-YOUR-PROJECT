export function formatCurrency(
  value: number,
  currency = "XOF",
  options: { compact?: boolean; maximumFractionDigits?: number } = {},
): string {
  const code = /^[A-Za-z]{3}$/.test(currency) ? currency.toUpperCase() : "XOF";
  const digits =
    options.maximumFractionDigits ??
    (code === "XOF" || code === "XAF" ? 0 : 2);
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: code,
    maximumFractionDigits: digits,
    notation: options.compact ? "compact" : "standard",
  }).format(value);
}

export function formatNumber(value: number, digits = 0): string {
  return new Intl.NumberFormat("fr-FR", {
    maximumFractionDigits: digits,
  }).format(value);
}

export function formatPercent(value: number, digits = 1): string {
  return new Intl.NumberFormat("fr-FR", {
    style: "percent",
    maximumFractionDigits: digits,
  }).format(value);
}

/**
 * Probabilité issue du moteur. Une borne empirique n'est jamais présentée
 * comme certaine : au-delà de 99,9 % (ou en dessous de 0,1 %) on affiche une
 * borne, pas « 100 % ».
 */
export function formatProbability(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "non disponible";
  }
  if (value >= 0.999) return "≥ 99,9 %";
  if (value > 0 && value <= 0.001) return "≤ 0,1 %";
  if (value <= 0) return "0 %";
  return formatPercent(value, digits);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function formatMicros(value: number): string {
  return `${(value / 1_000_000).toFixed(2)} USD`;
}

export function formatDuration(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  if (value < 1000) return `${Math.round(value)} ms`;
  return `${(value / 1000).toFixed(1)} s`;
}
