#!/usr/bin/env node
/*
 * Vérifie que la 3D reste hors du bundle initial et sous le budget phase 14.
 *
 * Prérequis : `vite build --manifest` (le script npm s'en charge).
 * - le chunk de Scene3D doit être un import dynamique, jamais importé par l'entrée ;
 * - la somme gzip du chunk + ses imports statiques doit rester < 1,2 Mo.
 */
import { readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { gzipSync } from "node:zlib";

const root = process.cwd();
const dist = join(root, "dist");
const manifestPath = join(dist, ".vite", "manifest.json");
const GB = 1024 * 1024;
const TARGET = 1.2 * GB;

let manifest;
try {
  manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
} catch {
  console.error(`manifest introuvable : ${manifestPath} (lancer vite build --manifest)`);
  process.exit(1);
}

const entries = Object.values(manifest);
const sceneEntry = entries.find((entry) =>
  String(entry.src ?? "").includes("Scene3D.tsx"),
);
if (!sceneEntry) {
  console.error("Scene3D introuvable dans le manifest : la 3D doit rester un chunk dédié.");
  process.exit(1);
}

function gzipSize(file) {
  return gzipSync(readFileSync(join(dist, file))).byteLength;
}

function collect(entry, seen = new Set()) {
  if (!entry || seen.has(entry.file)) return seen;
  seen.add(entry.file);
  for (const key of entry.imports ?? []) collect(manifest[key], seen);
  return seen;
}

const initial = new Set();
for (const entry of entries.filter((item) => item.isEntry)) {
  for (const file of collect(entry)) initial.add(file);
}

if (initial.has(sceneEntry.file)) {
  console.error(`Le chunk 3D est chargé au démarrage : ${sceneEntry.file}`);
  process.exit(1);
}

const threeFiles = collect(sceneEntry);
const extraFiles = [...threeFiles].filter((file) => !initial.has(file));
const total = extraFiles.reduce((sum, file) => sum + gzipSize(file), 0);
const size = (bytes) => `${(bytes / GB).toFixed(3)} Mo gzip`;

console.log(`Chunk 3D : ${sceneEntry.file} (${size(gzipSize(sceneEntry.file))})`);
for (const file of extraFiles) {
  if (file !== sceneEntry.file) console.log(`  + ${file} (${size(gzipSize(file))})`);
}
console.log(`Supplément 3D au chargement : ${size(total)} — budget ${size(TARGET)}`);
console.log(
  `Chunk initial : ${[...initial]
    .map((file) => `${file} (${size(gzipSize(file))})`)
    .join(", ")}`,
);

if (total > TARGET) {
  console.error("Budget dépassé : réduire les imports Three.js ou le chunk 3D.");
  process.exit(1);
}
if (!statSync(join(dist, sceneEntry.file)).isFile()) {
  console.error(`Fichier 3D absent : ${sceneEntry.file}`);
  process.exit(1);
}
