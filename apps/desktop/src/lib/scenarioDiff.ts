import { EVENT_CATALOG_BY_TYPE, type Metrics, type Scenario, type ScenarioEvent } from "@see/protocol";

import { ASSUMPTION_BY_KEY } from "./assumptions";

/**
 * Aplatissement et comparaison **purs** de scénarios (phase 13).
 *
 * Aucun calcul métier n'est fait ici : les valeurs proviennent du payload
 * sauvegardé. Seules des opérations de lecture, de tri et de soustraction
 * d'affichage sont autorisées. Les champs volatils (dates, identifiants de
 * rendu) sont ignorés pour éviter un diff bruyant.
 */

export type DiffEntryKind =
  | "added"
  | "removed"
  | "changed"
  | "event-added"
  | "event-removed"
  | "event-changed";

export interface DiffEntry {
  path: string;
  label: string;
  kind: DiffEntryKind;
  before?: unknown;
  after?: unknown;
}

export interface ScenarioLeaf {
  path: string;
  label: string;
  value: unknown;
}

export interface MetricComparison {
  key: string;
  label: string;
  unit: "currency" | "percent";
  before: number | null;
  after: number | null;
  delta: number | null;
  deltaPercent: number | null;
}

const DISTRIBUTION_FIELDS: Array<[string, string]> = [
  ["kind", "loi"],
  ["mean", "moyenne"],
  ["std", "écart-type"],
  ["sigma", "sigma"],
  ["low", "minimum"],
  ["mode", "mode"],
  ["high", "maximum"],
];

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function eventLabel(event: ScenarioEvent): string {
  return EVENT_CATALOG_BY_TYPE[event.type]?.label ?? event.type;
}

function assumptionLabel(key: string): string {
  return ASSUMPTION_BY_KEY.get(key)?.label ?? key;
}

function hypothesisLeaves(
  key: string,
  hypothesis: Record<string, unknown>,
): ScenarioLeaf[] {
  const base = `assumptions.${key}`;
  const label = assumptionLabel(key);
  const leaves: ScenarioLeaf[] = [];
  for (const [field, fieldLabel] of [
    ["value", "valeur"],
    ["min", "minimum"],
    ["max", "maximum"],
    ["confidence", "confiance"],
    ["source", "source"],
    ["description", "description"],
  ] as const) {
    if (hypothesis[field] !== undefined) {
      leaves.push({
        path: `${base}.${field}`,
        label: `${label} · ${fieldLabel}`,
        value: hypothesis[field],
      });
    }
  }
  const distribution = hypothesis.distribution;
  if (isPlainObject(distribution)) {
    for (const [field, fieldLabel] of DISTRIBUTION_FIELDS) {
      if (distribution[field] !== undefined) {
        leaves.push({
          path: `${base}.distribution.${field}`,
          label: `${label} · loi ${fieldLabel}`,
          value: distribution[field],
        });
      }
    }
  }
  return leaves.sort((left, right) => left.path.localeCompare(right.path));
}

function eventLeaves(event: ScenarioEvent): ScenarioLeaf[] {
  const base = `events[${event.id}]`;
  const label = eventLabel(event);
  const leaves: ScenarioLeaf[] = [];
  for (const [field, fieldLabel] of [
    ["type", "type"],
    ["startMonth", "mois de début"],
    ["durationMonths", "durée"],
    ["target", "cible"],
    ["mode", "mode"],
    ["probability", "probabilité"],
    ["enabled", "actif"],
  ] as const) {
    const value = (event as unknown as Record<string, unknown>)[field];
    if (value !== undefined) {
      leaves.push({
        path: `${base}.${field}`,
        label: `${label} · ${fieldLabel}`,
        value,
      });
    }
  }
  for (const [field, fieldLabel] of DISTRIBUTION_FIELDS) {
    const value = (event.magnitude as unknown as Record<string, unknown>)[field];
    if (value !== undefined) {
      leaves.push({
        path: `${base}.magnitude.${field}`,
        label: `${label} · intensité ${fieldLabel}`,
        value,
      });
    }
  }
  return leaves;
}

/**
 * Transforme un scénario en feuilles triées (`path`, `label`, `value`).
 * L'ordre est stable : champs d'en-tête, hypothèses triées par clé, puis
 * événements triés par identifiant.
 */
export function flattenScenario(scenario: Scenario): ScenarioLeaf[] {
  const leaves: ScenarioLeaf[] = [];
  for (const [field, label] of [
    ["name", "Nom"],
    ["model", "Modèle"],
    ["currency", "Devise"],
    ["horizonMonths", "Horizon (mois)"],
    ["notes", "Notes"],
  ] as const) {
    const value = (scenario as unknown as Record<string, unknown>)[field];
    if (value !== undefined) {
      leaves.push({ path: field, label, value });
    }
  }
  if (scenario.seasonality !== undefined && scenario.seasonality !== null) {
    leaves.push({
      path: "seasonality",
      label: "Saisonnalité",
      value: scenario.seasonality,
    });
  }
  const assumptions = scenario.assumptions ?? {};
  for (const key of Object.keys(assumptions).sort()) {
    leaves.push(...hypothesisLeaves(key, assumptions[key] as unknown as Record<string, unknown>));
  }
  const events = [...(scenario.events ?? [])].sort((left, right) =>
    left.id.localeCompare(right.id),
  );
  for (const event of events) {
    leaves.push(...eventLeaves(event));
  }
  return leaves;
}

function deepEqual(left: unknown, right: unknown): boolean {
  if (Object.is(left, right)) return true;
  if (Array.isArray(left) && Array.isArray(right)) {
    return (
      left.length === right.length &&
      left.every((item, index) => deepEqual(item, right[index]))
    );
  }
  if (isPlainObject(left) && isPlainObject(right)) {
    const leftKeys = Object.keys(left);
    const rightKeys = Object.keys(right);
    return (
      leftKeys.length === rightKeys.length &&
      leftKeys.every((key) => key in right && deepEqual(left[key], right[key]))
    );
  }
  return false;
}

function eventsById(scenario: Scenario): Map<string, ScenarioEvent> {
  return new Map((scenario.events ?? []).map((event) => [event.id, event]));
}

/**
 * Diff déterministe de deux scénarios. Une valeur identique n'apparaît pas.
 * Les événements ajoutés ou supprimés sont regroupés en une seule entrée.
 */
export function diffScenarios(a: Scenario, b: Scenario): DiffEntry[] {
  const entries: DiffEntry[] = [];

  const assumptionsA = a.assumptions ?? {};
  const assumptionsB = b.assumptions ?? {};
  const assumptionKeys = [
    ...new Set([...Object.keys(assumptionsA), ...Object.keys(assumptionsB)]),
  ].sort();
  for (const key of assumptionKeys) {
    const before = assumptionsA[key];
    const after = assumptionsB[key];
    if (before !== undefined && after === undefined) {
      entries.push({
        path: `assumptions.${key}`,
        label: assumptionLabel(key),
        kind: "removed",
        before,
      });
      continue;
    }
    if (before === undefined && after !== undefined) {
      entries.push({
        path: `assumptions.${key}`,
        label: assumptionLabel(key),
        kind: "added",
        after,
      });
      continue;
    }
    const leavesA = new Map(
      hypothesisLeaves(key, before as unknown as Record<string, unknown>).map((leaf) => [
        leaf.path,
        leaf,
      ]),
    );
    const leavesB = new Map(
      hypothesisLeaves(key, after as unknown as Record<string, unknown>).map((leaf) => [
        leaf.path,
        leaf,
      ]),
    );
    for (const path of [...new Set([...leavesA.keys(), ...leavesB.keys()])].sort()) {
      const left = leavesA.get(path);
      const right = leavesB.get(path);
      if (left && right && deepEqual(left.value, right.value)) continue;
      entries.push({
        path,
        label: (right ?? left)!.label,
        kind: left ? (right ? "changed" : "removed") : "added",
        ...(left ? { before: left.value } : {}),
        ...(right ? { after: right.value } : {}),
      });
    }
  }

  const eventsA = eventsById(a);
  const eventsB = eventsById(b);
  const eventIds = [...new Set([...eventsA.keys(), ...eventsB.keys()])].sort();
  for (const id of eventIds) {
    const before = eventsA.get(id);
    const after = eventsB.get(id);
    if (before && !after) {
      entries.push({
        path: `events[${id}]`,
        label: eventLabel(before),
        kind: "event-removed",
        before,
      });
      continue;
    }
    if (!before && after) {
      entries.push({
        path: `events[${id}]`,
        label: eventLabel(after),
        kind: "event-added",
        after,
      });
      continue;
    }
    const leavesA = new Map(eventLeaves(before!).map((leaf) => [leaf.path, leaf]));
    const leavesB = new Map(eventLeaves(after!).map((leaf) => [leaf.path, leaf]));
    for (const path of [...new Set([...leavesA.keys(), ...leavesB.keys()])].sort()) {
      const left = leavesA.get(path);
      const right = leavesB.get(path);
      if (left && right && deepEqual(left.value, right.value)) continue;
      entries.push({
        path,
        label: (right ?? left)!.label,
        kind: "event-changed",
        ...(left ? { before: left.value } : {}),
        ...(right ? { after: right.value } : {}),
      });
    }
  }

  const ignoredTopLevel = new Set(["schemaVersion", "assumptions", "events"]);
  const topA = new Map(
    flattenScenario(a)
      .filter((leaf) => !ignoredTopLevel.has(leaf.path) && !leaf.path.includes("."))
      .map((leaf) => [leaf.path, leaf]),
  );
  const topB = new Map(
    flattenScenario(b)
      .filter((leaf) => !ignoredTopLevel.has(leaf.path) && !leaf.path.includes("."))
      .map((leaf) => [leaf.path, leaf]),
  );
  for (const path of [...new Set([...topA.keys(), ...topB.keys()])].sort()) {
    const left = topA.get(path);
    const right = topB.get(path);
    if (left && right && deepEqual(left.value, right.value)) continue;
    entries.push({
      path,
      label: (right ?? left)!.label,
      kind: left ? (right ? "changed" : "removed") : "added",
      ...(left ? { before: left.value } : {}),
      ...(right ? { after: right.value } : {}),
    });
  }

  return entries;
}

function delta(before: number | null, after: number | null): {
  delta: number | null;
  deltaPercent: number | null;
} {
  if (before === null || after === null) return { delta: null, deltaPercent: null };
  const difference = after - before;
  return {
    delta: difference,
    deltaPercent: before === 0 ? null : difference / Math.abs(before),
  };
}

/**
 * Deltas d'affichage entre deux payloads de métriques. La soustraction est
 * autorisée ; aucune simulation n'est relancée.
 */
export function compareMetrics(before: Metrics, after: Metrics): MetricComparison[] {
  const rows: Array<{
    key: string;
    label: string;
    unit: MetricComparison["unit"];
    pick: (metrics: Metrics) => number | null | undefined;
  }> = [
    { key: "profit_p10", label: "Profit P10", unit: "currency", pick: (m) => m.p10 },
    { key: "profit_p50", label: "Profit P50", unit: "currency", pick: (m) => m.p50 },
    { key: "profit_p90", label: "Profit P90", unit: "currency", pick: (m) => m.p90 },
    {
      key: "break_even_probability",
      label: "Probabilité de point mort",
      unit: "percent",
      pick: (m) => m.breakEvenProbability,
    },
    {
      key: "financing_need_p50",
      label: "Besoin de financement P50",
      unit: "currency",
      pick: (m) => m.financingNeedP50,
    },
    {
      key: "cash_negative_probability",
      label: "P(trésorerie < 0)",
      unit: "percent",
      pick: (m) => m.cashNegativeProbability,
    },
  ];
  return rows.map((row) => {
    const left = row.pick(before);
    const right = row.pick(after);
    const numericBefore = left === null || left === undefined ? null : left;
    const numericAfter = right === null || right === undefined ? null : right;
    return {
      key: row.key,
      label: row.label,
      unit: row.unit,
      before: numericBefore,
      after: numericAfter,
      ...delta(numericBefore, numericAfter),
    };
  });
}
