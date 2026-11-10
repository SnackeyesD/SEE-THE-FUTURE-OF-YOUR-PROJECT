import { createHash } from "node:crypto";
import { copyFile, mkdir, readFile, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const pyodideRoot = dirname(require.resolve("pyodide/package.json"));
const destination = join(repoRoot, "apps/desktop/public/pyodide");
const coreFiles = [
  "pyodide.asm.js",
  "pyodide.asm.wasm",
  "pyodide-lock.json",
  "python_stdlib.zip",
  "pyodide.mjs",
  "pyodide.js",
];

const lock = JSON.parse(await readFile(join(pyodideRoot, "pyodide-lock.json"), "utf8"));
const baseUrl = `https://cdn.jsdelivr.net/pyodide/v${lock.info.version}/full/`;
const requested = ["numpy", "pandas"];
const packages = new Map();

function collect(name) {
  if (packages.has(name)) return;
  const entry = lock.packages[name];
  if (!entry) throw new Error(`paquet Pyodide inconnu: ${name}`);
  packages.set(name, entry);
  for (const dependency of entry.depends) collect(dependency);
}

for (const name of requested) collect(name);

await mkdir(destination, { recursive: true });

for (const file of coreFiles) {
  await copyFile(join(pyodideRoot, file), join(destination, file));
}

for (const entry of packages.values()) {
  const target = join(destination, entry.file_name);
  let buffer;
  try {
    buffer = await readFile(target);
  } catch {
    buffer = undefined;
  }
  if (!buffer) {
    const response = await fetch(`${baseUrl}${entry.file_name}`);
    if (!response.ok) {
      throw new Error(`téléchargement échoué (${response.status}): ${entry.file_name}`);
    }
    buffer = Buffer.from(await response.arrayBuffer());
  }
  const digest = createHash("sha256").update(buffer).digest("hex");
  if (digest !== entry.sha256) {
    throw new Error(`empreinte invalide pour ${entry.file_name}`);
  }
  await writeFile(target, buffer);
}

process.stdout.write(
  `Pyodide ${lock.info.version} prêt dans ${destination} (${packages.size} paquets)\n`,
);
