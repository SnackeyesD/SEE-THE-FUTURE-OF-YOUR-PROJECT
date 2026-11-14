#!/usr/bin/env node
/**
 * Banc d'essai UI (phase 01).
 *
 * La mesure réelle (fps pendant un glissement, latence de mise à jour d'un
 * graphique) exige une infrastructure navigateur (Playwright + shim IPC
 * déterministe) qui n'existe pas encore : elle est créée en phase 08 (Vitest)
 * puis en phase 16 (Playwright). Ce script ne simule donc aucune mesure : il
 * produit un rapport explicite `skipped` et vérifie ce qui peut l'être sans
 * navigateur (présence des composants de dataviz, taille du bundle si un build
 * existe).
 *
 * Usage :
 *   node scripts/perf/bench_ui.mjs --json-out docs/perf/ui.json
 */

import { existsSync, mkdirSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");

function parseArgs(argv) {
  const args = { jsonOut: null };
  for (let index = 0; index < argv.length; index += 1) {
    if (argv[index] === "--json-out") {
      args.jsonOut = argv[index + 1] ?? null;
      index += 1;
    }
  }
  return args;
}

function directorySize(root) {
  if (!existsSync(root)) return null;
  let total = 0;
  const stack = [root];
  while (stack.length > 0) {
    const current = stack.pop();
    for (const entry of readdirSync(current, { withFileTypes: true })) {
      const path = join(current, entry.name);
      if (entry.isDirectory()) stack.push(path);
      else if (entry.isFile()) total += statSync(path).size;
    }
  }
  return total;
}

const VIZ_DIR = join(REPO_ROOT, "packages", "ui", "src", "viz");
const DIST_DIR = join(REPO_ROOT, "apps", "desktop", "dist");

function vizInventory() {
  if (!existsSync(VIZ_DIR)) return { available: false, components: [] };
  const components = readdirSync(VIZ_DIR)
    .filter((name) => name.endsWith(".tsx") || name.endsWith(".ts"))
    .sort();
  return { available: true, components };
}

function playwrightAvailable() {
  try {
    // Résolution volontairement souple : l'infrastructure n'existe pas encore.
    const resolved = import.meta.resolve?.("playwright");
    return Boolean(resolved);
  } catch {
    return false;
  }
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const viz = vizInventory();
  const bundleBytes = directorySize(DIST_DIR);
  const hasPlaywright = playwrightAvailable();

  const report = {
    kind: "ui",
    status: "skipped",
    skipReason:
      "aucune infrastructure navigateur (Playwright + shim IPC déterministe) : " +
      "la mesure fps/latence serait inventée. Créée en phase 08 (Vitest) puis 16 (Playwright).",
    infrastructure: {
      playwrightAvailable: hasPlaywright,
      distExists: bundleBytes !== null,
      vizComponents: viz.components,
    },
    measurements: {
      fpsWhileDragging: null,
      chartUpdateMs: null,
      bundleBytes: bundleBytes === null ? null : bundleBytes,
      bundleKiB: bundleBytes === null ? null : Math.round((bundleBytes / 1024) * 10) / 10,
    },
    plannedMetrics: [
      "fps médian pendant un glissement de curseur (cible 30–60 i/s)",
      "temps de mise à jour du FanChart 36 points + 3 fantômes (cible ≤ 16 ms)",
      "temps de traitement d'un partiel (cible ≤ 4 ms)",
      "mémoire UI (cible < 100 Mo)",
      "taille du chunk 3D gzip (cible < 1,2 Mo, phase 14)",
    ],
    nextPhase: "08 pour l'outillage UI, 16 pour les E2E et les mesures de release",
  };

  const text = JSON.stringify(report, null, 2);
  if (args.jsonOut) {
    const out = resolve(REPO_ROOT, args.jsonOut);
    mkdirSync(dirname(out), { recursive: true });
    writeFileSync(out, `${text}\n`, "utf8");
  }

  console.log("UI : mesure ignorée (pas d'infrastructure navigateur en phase 01).");
  console.log(`Composants @see/ui/viz : ${viz.components.length}`);
  if (bundleBytes !== null) {
    console.log(`Bundle dist : ${report.measurements.bundleKiB} Kio`);
  } else {
    console.log("Bundle dist : absent (build non lancé)");
  }
  return 0;
}

process.exit(main());
