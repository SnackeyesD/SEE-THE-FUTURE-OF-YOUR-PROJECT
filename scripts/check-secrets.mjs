#!/usr/bin/env node
/**
 * Détection de secrets et de clés privées dans les sources versionnables.
 *
 * Le script ne lit jamais un fichier ignoré par Git (`.env`, base locale,
 * artefacts) : il s'appuie sur `git ls-files`, donc il ne peut pas divulguer un
 * secret local dans la sortie. Les tests et fixtures sont exclus : ils
 * contiennent volontairement de fausses clés pour vérifier le masquage.
 *
 * Sortie : un fichier et un motif, jamais la valeur détectée.
 */
import { execFileSync } from "node:child_process";
import { readFileSync, statSync } from "node:fs";
import { extname } from "node:path";

const EXCLUDED_EXTENSIONS = new Set([
  ".png",
  ".jpg",
  ".jpeg",
  ".gif",
  ".ico",
  ".pdf",
  ".woff",
  ".woff2",
  ".ttf",
  ".otf",
  ".zip",
  ".gz",
  ".db",
  ".sqlite",
  ".simproj",
  ".lock",
]);

const EXCLUDED_PATTERNS = [
  /(^|\/)node_modules\//,
  /(^|\/)dist\//,
  /(^|\/)target\//,
  /(^|\/)\.venv\//,
  /(^|\/)__pycache__\//,
  /(^|\/)tests?\//,
  /\.test\.(ts|tsx|js|mjs)$/,
  /(^|\/)docs\/perf\/archive\//,
  /(^|\/)package-lock\.json$/,
  /(^|\/)uv\.lock$/,
  /(^|\/)Cargo\.lock$/,
];

const RULES = [
  ["clé OpenAI", /\bsk-[A-Za-z0-9_-]{20,}/g],
  ["clé Google", /\bAIza[0-9A-Za-z_-]{30,}/g],
  ["jeton GitHub", /\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})/g],
  ["jeton Slack", /\bxox[baprs]-[A-Za-z0-9-]{15,}/g],
  ["clé privée PEM", /-----BEGIN (?:RSA |OPENSSH |EC |PGP )?PRIVATE KEY-----/g],
  ["affectation de clé", /\b(?:api[_-]?key|access[_-]?token|client[_-]?secret)\b\s*[:=]\s*["'][A-Za-z0-9_\-./+]{20,}["']/gi],
];

function trackedFiles() {
  const output = execFileSync("git", ["ls-files", "-z"], { encoding: "utf8" });
  return output.split("\0").filter(Boolean);
}

function included(path) {
  if (EXCLUDED_EXTENSIONS.has(extname(path).toLowerCase())) return false;
  return !EXCLUDED_PATTERNS.some((pattern) => pattern.test(path));
}

function lineNumber(text, index) {
  return text.slice(0, index).split("\n").length;
}

const findings = [];
for (const path of trackedFiles()) {
  if (!included(path)) continue;
  let info;
  try {
    info = statSync(path);
  } catch {
    continue;
  }
  if (!info.isFile() || info.size > 2 * 1024 * 1024) continue;
  const content = readFileSync(path, "utf8");
  for (const [label, pattern] of RULES) {
    pattern.lastIndex = 0;
    const match = pattern.exec(content);
    if (match) {
      findings.push({ path, line: lineNumber(content, match.index), label });
    }
  }
}

if (findings.length === 0) {
  console.log("✓ secrets:check — aucun secret apparent dans les fichiers suivis.");
  process.exit(0);
}

console.error("✗ secrets:check — secrets potentiels détectés (valeurs masquées) :");
for (const finding of findings) {
  console.error(`  ${finding.path}:${finding.line} — ${finding.label}`);
}
console.error(
  "Retirer le secret du fichier, le révoquer, puis le stocker uniquement dans le trousseau.",
);
process.exit(1);
