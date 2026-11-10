/**
 * GENERATED from src/tokens.css — ne pas éditer à la main.
 * Régénérer : npm run generate -w @see/ui   (vérifier : npm run check -w @see/ui)
 * Miroir TypeScript des tokens de couleur, pour les cas où la valeur
 * est nécessaire en JS/TS (charts SVG, canvas, exports).
 */

export const ink = {
  "ink-0": "#0b0e14",
  "ink-1": "#10141c",
  "ink-2": "#161b26",
  "ink-3": "#1e2431",
  "ink-inset": "#0d1118",
} as const;

export const line = {
  "line-0": "#242b38",
  "line-1": "#2f3849",
  "line-2": "#3c465a",
} as const;

export const text = {
  "text-0": "#e9edf5",
  "text-1": "#9aa3b6",
  "text-2": "#6e7789",
} as const;

export const signals = {
  accent: "#22d3ee",
  ok: "#34d399",
  warn: "#fbbf24",
  danger: "#f87171",
} as const;

/** Coloration syntaxique du sandbox et des logs. */
export const code = {
  "code-gutter": "#55617c",
  "code-comment": "#7fa087",
  "code-string": "#d9a66a",
  "code-keyword": "#79a8ff",
  "code-builtin": "#50c8c8",
  "code-number": "#e6a7e8",
} as const;

/**
 * Les 10 séries de données catégorielles, dans l'ordre d'attribution
 * par défaut. Attribution STABLE : une entité (scénario, hypothèse…)
 * garde sa couleur entre les rendus — passer un index fixe, jamais
 * l'ordre du tableau courant.
 */
export const SERIES: ReadonlyArray<{ name: string; color: string; fill: string | null }> = [
  { name: "series-1", color: "#4f8ef7", fill: null },
  { name: "series-2", color: "#2ec47f", fill: null },
  { name: "series-3", color: "#f6cd45", fill: null },
  { name: "series-4", color: "#ab8ff7", fill: null },
  { name: "series-5", color: "#f07db8", fill: null },
  { name: "series-6", color: "#ef5f45", fill: null },
  { name: "series-7", color: "#c5ea55", fill: null },
  { name: "series-8", color: "#0f6b80", fill: null },
  { name: "series-9", color: "#b83a3a", fill: null },
  { name: "series-10", color: "#7a9e4f", fill: null },
];

/** Couleur de la série d'index donné (modulo 10, stable). */
export function seriesColor(index: number): string {
  return SERIES[((index % SERIES.length) + SERIES.length) % SERIES.length].color;
}

/** Remplissage de distribution de la série d'index donné. */
export function seriesFill(index: number): string {
  const fill = SERIES[((index % SERIES.length) + SERIES.length) % SERIES.length].fill;
  return fill ?? seriesColor(index);
}
