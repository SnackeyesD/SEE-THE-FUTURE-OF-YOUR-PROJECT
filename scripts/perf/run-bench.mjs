#!/usr/bin/env node
/**
 * Orchestrateur du banc d'essai (phase 01).
 *
 * Exécute les trois bancs, agrège les résultats dans `docs/perf/latest.json` et
 * produit un résumé lisible `docs/perf/latest.md`.
 *
 * Usage :
 *   npm run bench
 *   npm run bench -- --skip-ui
 */

import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PERF_DIR = join(REPO_ROOT, "docs", "perf");

function parseArgs(argv) {
  const args = { skipEngine: false, skipSidecar: false, skipUi: false };
  for (const value of argv) {
    if (value === "--skip-engine") args.skipEngine = true;
    if (value === "--skip-sidecar") args.skipSidecar = true;
    if (value === "--skip-ui") args.skipUi = true;
  }
  return args;
}

function run(command, commandArgs, label) {
  console.log(`\n▶ ${label}`);
  const result = spawnSync(command, commandArgs, {
    cwd: REPO_ROOT,
    stdio: "inherit",
    env: process.env,
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`${label} a échoué (code ${result.status ?? "inconnu"})`);
  }
}

function readJson(path) {
  return JSON.parse(readFileSync(path, "utf8"));
}

function gitCommit() {
  const result = spawnSync("git", ["rev-parse", "--short", "HEAD"], {
    cwd: REPO_ROOT,
    encoding: "utf8",
  });
  return result.status === 0 ? result.stdout.trim() : null;
}

function isoNow() {
  return new Date().toISOString();
}

function medianOf(measurement) {
  return measurement?.median ?? null;
}

function formatMs(value) {
  return value === null || value === undefined ? "—" : `${value} ms`;
}

function formatMb(value) {
  return value === null || value === undefined ? "—" : `${value} Mo`;
}

function buildMarkdown(report) {
  const { machine, engine, sidecar, ui } = report;
  const lines = [];
  lines.push("# Baseline de performance — V3");
  lines.push("");
  lines.push(`> Généré par \`npm run bench\` le ${report.generatedAt}.`);
  lines.push("> Ne pas éditer à la main : relancer le banc d'essai.");
  lines.push("");
  lines.push("## Machine et versions");
  lines.push("");
  lines.push("| Élément | Valeur |");
  lines.push("|---|---|");
  lines.push(`| CPU | ${machine.cpu ?? "—"} (${machine.cpuCount ?? "—"} threads) |`);
  lines.push(`| RAM | ${machine.memTotalMb ?? "—"} Mo |`);
  lines.push(`| OS | ${machine.platform ?? "—"} |`);
  lines.push(`| Python | ${machine.python ?? "—"} |`);
  lines.push(`| NumPy | ${machine.numpy ?? "—"} |`);
  lines.push(`| Moteur | ${machine.engineVersion ?? "—"} |`);
  lines.push(`| Protocole | ${sidecar?.sidecar?.protocolVersion ?? "—"} |`);
  lines.push(`| Commit | ${report.commit ?? "—"} |`);
  lines.push("");

  if (engine) {
    const m = engine.measurements;
    lines.push("## Moteur (in-process)");
    lines.push("");
    lines.push("| Mesure | Médiane | Min | Max |");
    lines.push("|---|---|---|---|");
    lines.push(`| draft 500 × 36 | ${formatMs(medianOf(m.draft500x36))} | ${formatMs(m.draft500x36?.min)} | ${formatMs(m.draft500x36?.max)} |`);
    lines.push(`| final 5 000 × 36 | ${formatMs(medianOf(m.final5000x36))} | ${formatMs(m.final5000x36?.min)} | ${formatMs(m.final5000x36?.max)} |`);
    lines.push(`| large 20 000 × 36 | ${formatMs(medianOf(m.large20000x36))} | ${formatMs(m.large20000x36?.min)} | ${formatMs(m.large20000x36?.max)} |`);
    lines.push(`| surface proxy 15×15 × 200 | ${formatMs(m.surfaceProxy15x15x200?.elapsedMs)} (${m.surfaceProxy15x15x200?.cells} cellules) | — | — |`);
    lines.push("");
    lines.push(`- Payload final 5 000 runs : **${engine.payload.final5000KiB} Kio**.`);
    lines.push(`- Mémoire du processus de bench : **${formatMb(engine.memory.maxRssMb)}**.`);
    lines.push(`- Progression : ${engine.progress.callbacks} callback(s) pour 500 runs.`);
    const partials = engine.partials;
    if (partials) {
      lines.push(
        `- Partiels : ${partials.count} messages, payload max **${partials.maxPayloadKiB} Kio**, calcul max **${formatMs(partials.maxBuildMs)}**, écart max **${formatMs(partials.maxGapMs)}**.`,
      );
    }
    const cancellation = engine.cancellation;
    lines.push(
      `- Annulation : ${cancellation.status}, médiane **${formatMs(cancellation.median)}**, max **${formatMs(cancellation.max)}** après ${cancellation.completedRuns?.[0] ?? "—"} runs.`,
    );
    const convergence = engine.convergence;
    if (convergence) {
      lines.push(
        `- Convergence (\`${convergence.quality}\`) : ${convergence.converged ? "oui" : "non"}, stabilité ${convergence.stability}, ${convergence.stableBlocks} bloc(s) stable(s).`,
      );
    }
    const audit = engine.auditObservations?.valueIgnoredWhenDistributionSet;
    if (audit) {
      lines.push(
        `- Audit : \`value\` ${audit.identical ? "**ignoré**" : "pris en compte"} quand une distribution existe.`,
      );
    }
    lines.push("");
  } else {
    lines.push("## Moteur");
    lines.push("");
    lines.push("_Non mesuré (banc moteur ignoré ou en échec)._");
    lines.push("");
  }

  if (sidecar) {
    const m = sidecar.measurements;
    lines.push("## Sidecar (JSON-RPC sur stdio)");
    lines.push("");
    lines.push("| Mesure | Médiane | Min | Max |");
    lines.push("|---|---|---|---|");
    lines.push(`| ping au repos | ${formatMs(medianOf(m.pingAtRest))} | ${formatMs(m.pingAtRest?.min)} | ${formatMs(m.pingAtRest?.max)} |`);
    lines.push(`| draft 500 × 36 via RPC | ${formatMs(medianOf(m.draft500x36OverRpc))} | ${formatMs(m.draft500x36OverRpc?.min)} | ${formatMs(m.draft500x36OverRpc?.max)} |`);
    lines.push(`| final 5 000 × 36 via RPC | ${formatMs(medianOf(m.final5000x36OverRpc))} | ${formatMs(m.final5000x36OverRpc?.min)} | ${formatMs(m.final5000x36OverRpc?.max)} |`);
    lines.push("");
    lines.push(`- Démarrage (process → \`health\`) : **${formatMs(sidecar.sidecar.startupMs)}**.`);
    lines.push(`- **Blocage mono-thread** : un \`ping\` envoyé pendant un calcul 50 000 × 36 attend **${formatMs(m.pingDuring50000x36?.blockedMs)}**. Constat C3, correction en phase 06.`);
    lines.push(`- Mémoire RSS : ${formatMb(sidecar.memory.rssBeforeMb)} → ${formatMb(sidecar.memory.rssAfterMb)}.`);
    lines.push(`- Annulation : ${sidecar.limitations.cancellation}.`);
    lines.push("");
  } else {
    lines.push("## Sidecar");
    lines.push("");
    lines.push("_Non mesuré (banc sidecar ignoré ou en échec)._");
    lines.push("");
  }

  if (ui) {
    lines.push("## UI");
    lines.push("");
    if (ui.status === "skipped") {
      lines.push(`- **Mesure ignorée** : ${ui.skipReason}`);
      lines.push(`- Composants \`@see/ui/viz\` présents : ${ui.infrastructure.vizComponents.length}.`);
      lines.push(
        `- Bundle \`apps/desktop/dist\` : ${ui.measurements.bundleKiB === null ? "absent (build non lancé)" : `${ui.measurements.bundleKiB} Kio`}.`,
      );
      lines.push("- Mesures prévues :");
      for (const metric of ui.plannedMetrics) {
        lines.push(`  - ${metric}`);
      }
    } else {
      lines.push(`- Statut : ${ui.status}.`);
    }
    lines.push("");
  } else {
    lines.push("## UI");
    lines.push("");
    lines.push("_Non mesuré (banc UI ignoré ou en échec)._");
    lines.push("");
  }

  lines.push("## Lecture et limites");
  lines.push("");
  lines.push("- Les mesures moteur sont **in-process** ; celles du sidecar incluent JSON-RPC et la validation.");
  lines.push("- Le « surface proxy » rend les deux axes déterministes (`distribution = None`) : il mesure le **temps**, pas une vraie surface en tirages communs (phase 11).");
  lines.push("- Le moteur expose depuis la phase 04 l'annulation et les partiels ; leur transport JSON-RPC reste planifié en phase 06.");
  lines.push("- L'écart entre partiels inclut le calcul du bloc courant, pas seulement la construction du partiel.");
  lines.push("- Une mesure UI réelle exige un navigateur piloté ; elle est planifiée en phase 08/16.");
  lines.push("- Comparer deux exécutions sur la **même machine** ; les durées varient avec la charge système.");
  lines.push("");
  return `${lines.join("\n")}\n`;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  mkdirSync(PERF_DIR, { recursive: true });

  const engineOut = join(PERF_DIR, "engine.json");
  const sidecarOut = join(PERF_DIR, "sidecar.json");
  const uiOut = join(PERF_DIR, "ui.json");

  if (!args.skipEngine) {
    run(
      "uv",
      [
        "run",
        "--project",
        "packages/engine",
        "python",
        "packages/engine/bench/bench_engine.py",
        "--json-out",
        "docs/perf/engine.json",
      ],
      "Banc moteur",
    );
  }

  if (!args.skipSidecar) {
    run(
      "uv",
      [
        "run",
        "--project",
        "apps/desktop/src-tauri/sidecar",
        "python",
        "scripts/perf/bench_sidecar.py",
        "--json-out",
        "docs/perf/sidecar.json",
      ],
      "Banc sidecar",
    );
  }

  if (!args.skipUi) {
    run("node", ["scripts/perf/bench_ui.mjs", "--json-out", "docs/perf/ui.json"], "Banc UI");
  }

  const engine = !args.skipEngine && existsSync(engineOut) ? readJson(engineOut) : null;
  const sidecar = !args.skipSidecar && existsSync(sidecarOut) ? readJson(sidecarOut) : null;
  const ui = !args.skipUi && existsSync(uiOut) ? readJson(uiOut) : null;

  const report = {
    generatedAt: isoNow(),
    commit: gitCommit(),
    machine: engine?.machine ?? {
      cpu: null,
      cpuCount: null,
      memTotalMb: null,
      platform: null,
      python: null,
      numpy: null,
      engineVersion: null,
    },
    engine,
    sidecar,
    ui,
  };

  const latestJson = join(PERF_DIR, "latest.json");
  const latestMd = join(PERF_DIR, "latest.md");
  writeFileSync(latestJson, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  writeFileSync(latestMd, buildMarkdown(report), "utf8");

  console.log("\n✔ Baseline écrite :");
  console.log(`  - ${latestJson}`);
  console.log(`  - ${latestMd}`);
  console.log("  - docs/perf/engine.json, sidecar.json, ui.json");
  return 0;
}

try {
  process.exit(main());
} catch (error) {
  console.error(`\n✖ Banc d'essai interrompu : ${error.message}`);
  process.exit(1);
}
