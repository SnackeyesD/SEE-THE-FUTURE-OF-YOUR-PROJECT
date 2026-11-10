#!/usr/bin/env node
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(here, "..", "..", "..");
const schemaPath = resolve(repoRoot, "packages/protocol/schema/messages.schema.json");
const tsPath = resolve(repoRoot, "packages/protocol/src/generated.ts");
const pyPath = resolve(
  repoRoot,
  "apps/desktop/src-tauri/sidecar/sidecar/protocol_models.py",
);

const check = process.argv.includes("--check");
const schema = JSON.parse(readFileSync(schemaPath, "utf8"));
const defs = schema.$defs ?? {};
const defNames = Object.keys(defs);

if (defNames.length === 0) {
  console.error("No $defs found in the protocol schema.");
  process.exit(1);
}

function refName(ref) {
  return ref.split("/").pop();
}

function isEmptySchema(value) {
  return !value || Object.keys(value).length === 0;
}

function isObjectWithProps(value) {
  return (
    value &&
    value.type === "object" &&
    value.properties &&
    Object.keys(value.properties).length > 0
  );
}

function needsParens(value) {
  if (!value) return false;
  return Boolean(value.anyOf) || (Array.isArray(value.enum) && value.enum.length > 1);
}

function tsType(value) {
  if (isEmptySchema(value)) return "unknown";
  if (value.$ref) return refName(value.$ref);
  if ("const" in value) return JSON.stringify(value.const);
  if (value.enum) return value.enum.map((entry) => JSON.stringify(entry)).join(" | ");
  if (value.anyOf) return value.anyOf.map(tsType).join(" | ");
  if (value.type === "array") {
    const inner = tsType(value.items);
    return needsParens(value.items) ? `(${inner})[]` : `${inner}[]`;
  }
  switch (value.type) {
    case "string":
      return "string";
    case "integer":
    case "number":
      return "number";
    case "boolean":
      return "boolean";
    case "null":
      return "null";
    case "object": {
      if (isObjectWithProps(value)) {
        const required = new Set(value.required ?? []);
        const props = Object.entries(value.properties).map(
          ([name, prop]) => `${name}${required.has(name) ? "" : "?"}: ${tsType(prop)}`,
        );
        return `{ ${props.join("; ")} }`;
      }
      if (value.additionalProperties && typeof value.additionalProperties === "object") {
        return `Record<string, ${tsType(value.additionalProperties)}>`;
      }
      return "Record<string, unknown>";
    }
    default:
      return "unknown";
  }
}

function tsDefinition(name, value) {
  if (isObjectWithProps(value)) {
    const required = new Set(value.required ?? []);
    const props = Object.entries(value.properties).map(
      ([propName, prop]) => `  ${propName}${required.has(propName) ? "" : "?"}: ${tsType(prop)};`,
    );
    return `export interface ${name} {\n${props.join("\n")}\n}`;
  }
  return `export type ${name} = ${tsType(value)};`;
}

function pyLiteral(value) {
  if (typeof value === "string") return JSON.stringify(value);
  if (value === true) return "True";
  if (value === false) return "False";
  if (value === null) return "None";
  return String(value);
}

function pyType(value) {
  if (isEmptySchema(value)) return "Any";
  if (value.$ref) return refName(value.$ref);
  if ("const" in value) return `Literal[${pyLiteral(value.const)}]`;
  if (value.enum) return `Literal[${value.enum.map(pyLiteral).join(", ")}]`;
  if (value.anyOf) return value.anyOf.map(pyType).join(" | ");
  if (value.type === "array") return `list[${pyType(value.items)}]`;
  switch (value.type) {
    case "string":
      return "str";
    case "integer":
      return "int";
    case "number":
      return "float";
    case "boolean":
      return "bool";
    case "null":
      return "None";
    case "object": {
      if (isObjectWithProps(value)) return "dict[str, Any]";
      if (value.additionalProperties && typeof value.additionalProperties === "object") {
        return `dict[str, ${pyType(value.additionalProperties)}]`;
      }
      return "dict[str, Any]";
    }
    default:
      return "Any";
  }
}

function pyDefinition(name, value) {
  if (isObjectWithProps(value)) {
    const required = new Set(value.required ?? []);
    const fields = Object.entries(value.properties).map(([fieldName, field]) => {
      const type = pyType(field);
      if (required.has(fieldName)) return `    ${fieldName}: ${type}`;
      if (type === "Any" || type === "None") return `    ${fieldName}: ${type} = None`;
      const optionalType = type.split(" | ").includes("None") ? type : `${type} | None`;
      return `    ${fieldName}: ${optionalType} = None`;
    });
    return [
      `class ${name}(BaseModel):`,
      '    model_config = ConfigDict(extra="forbid")',
      "",
      ...(fields.length > 0 ? fields : ["    pass"]),
    ].join("\n");
  }
  if (value.enum) {
    const entries = value.enum.map((entry) => `    ${pyLiteral(entry)},`);
    return `${name} = Literal[\n${entries.join("\n")}\n]`;
  }
  return `${name} = ${pyType(value)}`;
}

const version = schema.version ?? "0.0.0";
const tsHeader = [
  "// AUTO-GENERATED FILE — DO NOT EDIT BY HAND.",
  "// Source: packages/protocol/schema/messages.schema.json",
  `// Protocol version: ${version}`,
  "// Regenerate with: npm run protocol:generate",
  "",
  `export const PROTOCOL_VERSION = ${JSON.stringify(version)};`,
  "",
].join("\n");

const pyHeader = [
  "# AUTO-GENERATED FILE — DO NOT EDIT BY HAND.",
  "# Source: packages/protocol/schema/messages.schema.json",
  `# Protocol version: ${version}`,
  "# Regenerate with: npm run protocol:generate",
  "",
  "from __future__ import annotations",
  "",
  "from typing import Any, Literal",
  "",
  "from pydantic import BaseModel, ConfigDict",
  "",
  `PROTOCOL_VERSION = ${JSON.stringify(version)}`,
  "",
  "",
].join("\n");

const tsBody = defNames.map((name) => tsDefinition(name, defs[name])).join("\n\n");
const pyBody = defNames.map((name) => pyDefinition(name, defs[name])).join("\n\n\n");
const tsContent = `${tsHeader}\n${tsBody}\n`;
const pyContent = `${pyHeader}${pyBody}\n`;

const outputs = [
  [tsPath, tsContent],
  [pyPath, pyContent],
];

let changed = false;
for (const [path, content] of outputs) {
  const current = existsSync(path) ? readFileSync(path, "utf8") : null;
  if (current === content) continue;
  changed = true;
  if (check) {
    console.error(`Out of date: ${path}`);
    continue;
  }
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, content, "utf8");
  console.log(`Generated ${path}`);
}

if (check) {
  if (changed) {
    console.error("Generated protocol files are out of date. Run: npm run protocol:generate");
    process.exit(1);
  }
  console.log("Generated protocol files are up to date.");
}
