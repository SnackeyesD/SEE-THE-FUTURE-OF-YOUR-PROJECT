import type { Metrics, Scenario } from "@see/protocol";
import { describe, expect, it } from "vitest";

import { compareMetrics, diffScenarios, flattenScenario } from "./scenarioDiff";

function base(): Scenario {
  return {
    name: "Base",
    model: "retail_depot",
    currency: "XOF",
    horizonMonths: 12,
    assumptions: {
      unit_price: { value: 5_000, min: 4_000, max: 6_000, confidence: 0.7 },
      unit_cost: { value: 3_000 },
    },
    events: [
      {
        id: "ev1",
        type: "supplier_price_rise",
        startMonth: 2,
        durationMonths: 3,
        target: "unit_cost",
        magnitude: { kind: "normal", mean: 1.1, std: 0.1 },
        probability: 0.4,
        enabled: true,
      },
    ],
  };
}

describe("flattenScenario", () => {
  it("produit un ordre stable et ignore les champs absents", () => {
    const leaves = flattenScenario(base());
    const paths = leaves.map((leaf) => leaf.path);

    expect(paths.slice(0, 4)).toEqual([
      "name",
      "model",
      "currency",
      "horizonMonths",
    ]);
    expect(paths).toContain("assumptions.unit_price.value");
    expect(paths).toContain("assumptions.unit_price.confidence");
    expect(paths).toContain("events[ev1].magnitude.mean");
    expect(paths).not.toContain("notes");
    expect(new Set(paths).size).toBe(paths.length);

    const assumptionPaths = paths.filter((path) => path.startsWith("assumptions."));
    expect(assumptionPaths).toEqual(
      [...assumptionPaths].sort((left, right) => left.localeCompare(right)),
    );
  });

  it("accepte des hypothèses nulles et une saisonnalité", () => {
    const leaves = flattenScenario({
      name: "Vide",
      assumptions: {},
      seasonality: [1, 0.8, 1.2],
    });
    expect(leaves.map((leaf) => leaf.path)).toEqual(["name", "seasonality"]);
  });
});

describe("diffScenarios", () => {
  it("ne signale rien pour deux scénarios identiques", () => {
    expect(diffScenarios(base(), base())).toEqual([]);
  });

  it("distingue ajout, suppression et modification", () => {
    const before = base();
    const after = base();
    after.assumptions = {
      unit_price: { value: 5_200, min: 4_000, max: 6_000, confidence: 0.7 },
      demand_mean_monthly: { value: 10 },
    };

    const entries = diffScenarios(before, after);
    const byPath = new Map(entries.map((entry) => [entry.path, entry]));

    expect(byPath.get("assumptions.unit_price.value")).toMatchObject({
      kind: "changed",
      before: 5_000,
      after: 5_200,
    });
    expect(byPath.get("assumptions.unit_cost")).toMatchObject({ kind: "removed" });
    expect(byPath.get("assumptions.demand_mean_monthly")).toMatchObject({
      kind: "added",
    });
    expect(entries.some((entry) => entry.path.includes("unit_price.min"))).toBe(false);
  });

  it("regroupe les événements ajoutés, supprimés et modifiés", () => {
    const before = base();
    const after = base();
    after.events = [
      {
        ...before.events![0],
        magnitude: { kind: "normal", mean: 1.2, std: 0.1 },
      },
      {
        id: "ev2",
        type: "competitor_entry",
        startMonth: 5,
        durationMonths: 2,
        target: "demand",
        magnitude: { kind: "triangular", low: 0.8, mode: 0.9, high: 1 },
      },
    ];

    const entries = diffScenarios(before, after);
    expect(
      entries.find((entry) => entry.path === "events[ev1].magnitude.mean"),
    ).toMatchObject({ kind: "event-changed", after: 1.2 });
    expect(entries.find((entry) => entry.path === "events[ev2]")).toMatchObject({
      kind: "event-added",
      label: expect.any(String),
    });

    const removed = diffScenarios(after, before);
    expect(
      removed.find((entry) => entry.path === "events[ev2]"),
    ).toMatchObject({ kind: "event-removed" });
  });

  it("détecte les changements d'en-tête et de saisonnalité", () => {
    const before = base();
    const after = { ...base(), horizonMonths: 18, seasonality: [1, 1, 1] };
    const entries = diffScenarios(before, after);

    expect(
      entries.find((entry) => entry.path === "horizonMonths"),
    ).toMatchObject({ kind: "changed", before: 12, after: 18 });
    expect(
      entries.find((entry) => entry.path === "seasonality"),
    ).toMatchObject({ kind: "added" });
  });
});

function metrics(overrides: Partial<Metrics> = {}): Metrics {
  return {
    meanProfit: 0,
    medianProfit: 0,
    stdProfit: 0,
    minProfit: 0,
    maxProfit: 0,
    p10: 1_000,
    p50: 2_000,
    p90: 3_000,
    lossProbability: 0.1,
    profitPositiveProbability: 0.9,
    meanRevenue: 0,
    meanCosts: 0,
    meanTax: 0,
    meanCashEnd: 0,
    meanUnitsSold: 0,
    meanUnitsLost: 0,
    meanStockoutMonths: 0,
    meanEndStock: 0,
    meanInventoryValue: 0,
    meanProfitMargin: 0,
    cashNegativeProbability: 0.2,
    financingNeedP50: 5_000,
    breakEvenProbability: 0.5,
    ...overrides,
  };
}

describe("compareMetrics", () => {
  it("calcule des deltas signés et des pourcentages", () => {
    const rows = compareMetrics(
      metrics(),
      metrics({ p50: 2_500, breakEvenProbability: 0.4 }),
    );
    const byKey = new Map(rows.map((row) => [row.key, row]));

    expect(byKey.get("profit_p50")).toMatchObject({
      before: 2_000,
      after: 2_500,
      delta: 500,
      deltaPercent: 0.25,
    });
    expect(byKey.get("break_even_probability")).toMatchObject({
      delta: expect.closeTo(-0.1, 6),
    });
    expect(byKey.get("profit_p10")?.delta).toBe(0);
  });

  it("renvoie des deltas nuls quand une valeur manque ou que la base est zéro", () => {
    const rows = compareMetrics(
      metrics({ financingNeedP50: undefined, p10: 0 }),
      metrics({ financingNeedP50: 1_000, p10: 500 }),
    );
    const byKey = new Map(rows.map((row) => [row.key, row]));

    expect(byKey.get("financing_need_p50")).toMatchObject({
      before: null,
      after: 1_000,
      delta: null,
      deltaPercent: null,
    });
    expect(byKey.get("profit_p10")).toMatchObject({
      delta: 500,
      deltaPercent: null,
    });
  });
});
