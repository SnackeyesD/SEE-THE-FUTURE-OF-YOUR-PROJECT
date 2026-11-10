import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(here, "..", "..", "..");
const schemaPath = resolve(repoRoot, "packages/protocol/schema/messages.schema.json");
const generatorPath = resolve(repoRoot, "packages/protocol/scripts/generate.mjs");
const tsPath = resolve(repoRoot, "packages/protocol/src/generated.ts");
const pyPath = resolve(
  repoRoot,
  "apps/desktop/src-tauri/sidecar/sidecar/protocol_models.py",
);

const schema = JSON.parse(readFileSync(schemaPath, "utf8"));

test("the schema declares a version and definitions", () => {
  assert.equal(typeof schema.version, "string");
  assert.ok(schema.version.length > 0);

  const names = Object.keys(schema.$defs ?? {});
  assert.ok(names.length >= 8);
  for (const expected of [
    "RequestId",
    "JSONRPCRequest",
    "JSONRPCResponse",
    "PingResult",
    "HealthResult",
    "SidecarStatus",
    "Scenario",
    "SimulationConfig",
    "SimulateParams",
    "SimulationResult",
  ]) {
    assert.ok(names.includes(expected), `missing definition ${expected}`);
  }

  assert.ok(schema.$defs.MethodName.enum.includes("simulate"));
  assert.ok(schema.$defs.MethodName.enum.includes("simulate.progress"));
});

test("generated files expose every definition", () => {
  const ts = readFileSync(tsPath, "utf8");
  const py = readFileSync(pyPath, "utf8");

  for (const name of Object.keys(schema.$defs)) {
    assert.ok(ts.includes(name), `TypeScript output is missing ${name}`);
    assert.ok(py.includes(name), `Python output is missing ${name}`);
  }
});

test("generated files are up to date", () => {
  const output = execFileSync(process.execPath, [generatorPath, "--check"], {
    cwd: repoRoot,
    encoding: "utf8",
  });
  assert.match(output, /up to date/i);
});
