#!/usr/bin/env node
/*
 * ui:check — garde-fous du design system « Ink & Signal » (refont phase 07).
 *
 * Fait échouer la CI si :
 *   1. un hex ou rgb()/rgba() est écrit en dehors des tokens
 *      (packages/ui/src/tokens.css, packages/ui/src/themes/, tokens.ts généré) ;
 *   2. une police littérale est référencée en dehors de tokens.css ;
 *   3. styles.css contient une classe composant gen-1 bannie ;
 *   4. styles.css contient une classe jamais référencée dans le TSX
 *      (style mort — à purger ou documenter dans refont/05…/residus-css.md).
 *
 * Usage : npm run ui:check
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";

const ROOT = process.cwd();
const errors = [];

/* ---------- collecte ---------- */
function walk(dir, exts, acc = []) {
  for (const name of readdirSync(dir)) {
    if (name === "node_modules" || name === "dist" || name.startsWith(".")) continue;
    const p = join(dir, name);
    const st = statSync(p);
    if (st.isDirectory()) walk(p, exts, acc);
    else if (exts.some((e) => name.endsWith(e))) acc.push(p);
  }
  return acc;
}

const cssFiles = walk(ROOT, [".css"]);
const tsFiles = [
  ...walk(join(ROOT, "apps"), [".tsx", ".ts"]),
  ...walk(join(ROOT, "packages"), [".tsx", ".ts"]),
];

// les sources de vérité (et le généré) ont le DROIT aux valeurs brutes
const TOKEN_FILES = /tokens\.css$|themes[\\/]light\.css$|tokens\.ts$/;

/* ---------- 1. couleurs brutes hors tokens ---------- */
const stripComments = (s) => s.replace(/\/\*[\s\S]*?\*\//g, "");
const COLOR_RE = /#[0-9a-fA-F]{3,8}\b|\brgba?\(/;

for (const f of cssFiles) {
  if (TOKEN_FILES.test(f)) continue;
  const body = stripComments(readFileSync(f, "utf8"));
  const lines = body.split("\n");
  lines.forEach((l, i) => {
    if (COLOR_RE.test(l)) errors.push(`${relative(ROOT, f)}:${i + 1} valeur brute (hex/rgb) hors tokens : ${l.trim().slice(0, 90)}`);
  });
}

for (const f of tsFiles) {
  if (TOKEN_FILES.test(f)) continue;
  const body = stripComments(readFileSync(f, "utf8"));
  const lines = body.split("\n");
  lines.forEach((l, i) => {
    if (COLOR_RE.test(l)) errors.push(`${relative(ROOT, f)}:${i + 1} valeur brute (hex/rgb) hors tokens : ${l.trim().slice(0, 90)}`);
  });
}

/* ---------- 2. polices littérales hors tokens ---------- */
for (const f of cssFiles) {
  if (f.endsWith("tokens.css")) continue;
  const body = stripComments(readFileSync(f, "utf8"));
  const lines = body.split("\n");
  lines.forEach((l, i) => {
    if (/font-family\s*:(?!.*var\()/.test(l) && !/font-family\s*:\s*var\(--/.test(l)) {
      if (/(?:font-family):[^;]*(?:["']|\b(?:Inter|system-ui|monospace|sans-serif|serif)\b)/.test(l)) {
        errors.push(`${relative(ROOT, f)}:${i + 1} police littérale (passer par --font-ui/--font-data) : ${l.trim().slice(0, 90)}`);
      }
    }
  });
}

/* ---------- 3. classes composant gen-1 bannies dans styles.css ---------- */
const stylesPath = join(ROOT, "apps", "desktop", "src", "styles.css");
const styles = stripComments(readFileSync(stylesPath, "utf8"));
const BANNED = [
  ".card ", ".card,", ".card:", ".card--ok", ".card h2",
  ".badge", ".button--", ".tabs", ".tab--", ".form-grid", ".form-row",
  ".form-span", ".budget-row", ".field-hint", ".facts", ".log__", ".log ",
  ".log,", ".log.", ".hint", ".error", ".muted", ".ok ", ".actions ",
  ".actions,", ".eyebrow", ".subtitle", ".header ", ".app ",
];
for (const b of BANNED) {
  if (styles.includes(b)) errors.push(`styles.css : classe gen-1 bannie réapparue : "${b.trim()}"`);
}

/* ---------- 4. styles morts : classe non référencée dans le TSX ---------- */
// classes définies dans styles.css (hors éléments purs)
const definedClasses = new Set();
for (const m of styles.matchAll(/\.([a-zA-Z][\w-]*)/g)) definedClasses.add(m[1]);
const uiClasses = new Set([...definedClasses].filter((c) => c.startsWith("ui-")));

const tsxBody = tsFiles
  .filter((f) => f.endsWith(".tsx"))
  .map((f) => readFileSync(f, "utf8"))
  .join("\n");

for (const c of definedClasses) {
  // les classes ui-* viennent de primitives.css (usage TSX vérifié là) ;
  // on ne vérifie ici que ce que styles.css possède réellement
  if (c.startsWith("ui-")) continue;
  const re = new RegExp(`\\b${c}\\b`);
  if (!re.test(tsxBody)) {
    errors.push(`styles.css : classe morte (jamais référencée dans le TSX) : .${c}`);
  }
}

/* ---------- verdict ---------- */
if (errors.length > 0) {
  console.error(`\n✗ ui:check — ${errors.length} violation(s) du design system :\n`);
  for (const e of errors) console.error(`  • ${e}`);
  console.error(
    "\nRègles : refont/07-adoption-nettoyage/DESIGN.md — les valeurs vivent\n" +
      "dans packages/ui/src/tokens.css (+ themes/), les composants dans @see/ui."
  );
  process.exit(1);
}
console.log("✓ ui:check — design system conforme (couleurs, polices, purge, styles morts)");
