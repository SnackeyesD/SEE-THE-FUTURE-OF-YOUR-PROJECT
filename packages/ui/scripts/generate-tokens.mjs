/**
 * Génère src/tokens.ts depuis src/tokens.css — source de vérité unique.
 * Usage : node scripts/generate-tokens.mjs [--check]
 * Discipline identique à packages/protocol (généré, jamais édité à la main).
 */
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const cssPath = join(here, "..", "src", "tokens.css");
const outPath = join(here, "..", "src", "tokens.ts");

const css = readFileSync(cssPath, "utf8");

/** Extrait { --nom: valeur } des déclarations de couleur du CSS. */
function extract(prefixes) {
  const re = /--([a-z0-9-]+):\s*([^;]+);/g;
  const tokens = {};
  let match;
  while ((match = re.exec(css)) !== null) {
    const [, name, raw] = match;
    const value = raw.trim();
    if (!prefixes.some((p) => name === p || name.startsWith(p + "-"))) continue;
    if (!/^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(value)) continue;
    tokens[name] = value;
  }
  return tokens;
}

const ink = extract(["ink"]);
const line = extract(["line"]);
const text = extract(["text"]);
const code = extract(["code"]);
const seriesTokens = extract(["series"]);

/** Regroupe { "series-1": "#4f9cf9", "series-1-fill": "rgb(...)" } en paires. */
const series = [];
for (let i = 1; i <= 10; i++) {
  const color = seriesTokens[`series-${i}`];
  const fill = seriesTokens[`series-${i}-fill`];
  if (!color) throw new Error(`--series-${i} manquant dans tokens.css`);
  series.push({ name: `series-${i}`, color, fill: fill ?? null });
}

/** Échappement des quotes pour l'emission TS. */
const q = (value) => `"${value.replace(/\\/g, "\\\\")}"`;

const objectOf = (tokens, indent) =>
  Object.entries(tokens)
    .map(([key, value]) => `${indent}"${key}": ${q(value)},`)
    .join("\n");

const seriesEntries = series
  .map(
    ({ name, color, fill }) => `  { name: ${q(name)}, color: ${q(color)}, fill: ${fill ? q(fill) : "null"} },`,
  )
  .join("\n");

const output = `/**
 * GENERATED from src/tokens.css — ne pas éditer à la main.
 * Régénérer : npm run generate -w @see/ui   (vérifier : npm run check -w @see/ui)
 * Miroir TypeScript des tokens de couleur, pour les cas où la valeur
 * est nécessaire en JS/TS (charts SVG, canvas, exports).
 */

export const ink = {
${objectOf(ink, "  ")}
} as const;

export const line = {
${objectOf(line, "  ")}
} as const;

export const text = {
${objectOf(text, "  ")}
} as const;

export const signals = {
  accent: ${q(extract(["accent"]).accent)},
  ok: ${q(extract(["ok"]).ok)},
  warn: ${q(extract(["warn"]).warn)},
  danger: ${q(extract(["danger"]).danger)},
} as const;

/** Coloration syntaxique du sandbox et des logs. */
export const code = {
${objectOf(code, "  ")}
} as const;

/**
 * Les 10 séries de données catégorielles, dans l'ordre d'attribution
 * par défaut. Attribution STABLE : une entité (scénario, hypothèse…)
 * garde sa couleur entre les rendus — passer un index fixe, jamais
 * l'ordre du tableau courant.
 */
export const SERIES: ReadonlyArray<{ name: string; color: string; fill: string | null }> = [
${seriesEntries}
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
`;

if (process.argv.includes("--check")) {
  const current = readFileSync(outPath, "utf8");
  if (current !== output) {
    console.error("tokens.ts n'est pas à jour de tokens.css. Lancer : npm run generate -w @see/ui");
    process.exit(1);
  }
  console.log("tokens.ts à jour.");
} else {
  writeFileSync(outPath, output);
  console.log(`tokens.ts généré (${series.length} séries).`);
}
