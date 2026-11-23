import type {
  Project,
  ProjectDataResult,
  Scenario,
  ScenarioRecord,
  SimulationResult,
  SimulationRunRecord,
} from "@see/protocol";

export const project: Project = {
  id: "project-1",
  name: "Dépôt de boissons",
  description: "Test de parcours critique",
  currency: "XOF",
  status: "active",
  createdAt: "2026-01-10T08:00:00.000Z",
  updatedAt: "2026-01-11T09:30:00.000Z",
  schemaVersion: 1,
  metadata: {},
};

export const scenario: Scenario = {
  schemaVersion: "1.0.0",
  name: "Scénario de base",
  model: "retail_depot",
  currency: "XOF",
  horizonMonths: 12,
  assumptions: {
    initial_cash: { value: 500_000, source: "test" },
    unit_price: { value: 5_000, source: "test" },
    unit_cost: { value: 3_000, source: "test" },
    fixed_costs_monthly: { value: 100_000, source: "test" },
    demand_mean_monthly: { value: 500, source: "test" },
  },
};

export const scenarioRecord: ScenarioRecord = {
  id: "scenario-1",
  projectId: project.id,
  name: "Scénario de base",
  model: "retail_depot",
  scenario,
  createdAt: "2026-01-10T08:05:00.000Z",
  updatedAt: "2026-01-10T08:05:00.000Z",
  archivedAt: null,
};

export const simulationResult: SimulationResult = {
  runId: "run-1",
  engineVersion: "0.2.0",
  scenarioName: "Scénario de base",
  model: "retail_depot",
  currency: "XOF",
  horizonMonths: 12,
  runs: 10_000,
  seed: 42,
  durationMs: 1234,
  metrics: {
    meanProfit: 250_000,
    medianProfit: 240_000,
    stdProfit: 50_000,
    minProfit: -100_000,
    maxProfit: 500_000,
    p10: 150_000,
    p50: 240_000,
    p90: 350_000,
    lossProbability: 0.12,
    profitPositiveProbability: 0.88,
    meanRevenue: 1_000_000,
    meanCosts: 750_000,
    meanTax: 25_000,
    meanCashEnd: 600_000,
    meanUnitsSold: 500,
    meanUnitsLost: 20,
    meanStockoutMonths: 0.5,
    meanEndStock: 120,
    meanInventoryValue: 60_000,
    meanProfitMargin: 0.25,
    cashNegativeProbability: 0.05,
    meanMinCash: 200_000,
    minCashP10: 100_000,
    minCashP50: 220_000,
    minCashP90: 300_000,
    financingNeedP50: 0,
    financingNeedP90: 0,
    breakEvenProbability: 0.9,
    medianBreakEvenMonth: 6,
    minCashCdf: [
      { value: 0, probability: 0.05 },
      { value: 200_000, probability: 0.5 },
    ],
  },
  histogram: {
    bins: [
      { lower: -100_000, upper: 0, count: 1_200, probability: 0.12 },
      { lower: 0, upper: 100_000, count: 2_300, probability: 0.23 },
      { lower: 100_000, upper: 300_000, count: 4_500, probability: 0.45 },
      { lower: 300_000, upper: 500_000, count: 2_000, probability: 0.2 },
    ],
  },
  monthly: {
    values: [
      {
        index: 0,
        month: 1,
        meanRevenue: 80_000,
        meanProfit: 15_000,
        meanDemand: 500,
        meanUnitsSold: 480,
        meanStockEnd: 120,
        stockoutProbability: 0.05,
        profitP10: 5_000,
        profitP50: 15_000,
        profitP90: 25_000,
        cashP10: 450_000,
        cashP50: 515_000,
        cashP90: 560_000,
        breakEvenProbability: 0,
        profitHistogram: null,
        cashHistogram: null,
      },
    ],
  },
  sensitivity: [
    { hypothesis: "demand_mean_monthly", correlation: 0.72, contribution: 120_000 },
    { hypothesis: "unit_price", correlation: 0.45, contribution: 80_000 },
  ],
  breakEven: {
    monthlyFixedCosts: 100_000,
    unitMargin: 2_000,
    breakEvenUnitsMonthly: 50,
    breakEvenRevenueMonthly: 250_000,
  },
  approximations: null,
};

export const runRecord: SimulationRunRecord = {
  id: "run-1",
  projectId: project.id,
  scenarioId: scenarioRecord.id,
  engineVersion: simulationResult.engineVersion,
  seed: simulationResult.seed,
  runs: simulationResult.runs,
  durationMs: simulationResult.durationMs,
  summary: {},
  result: simulationResult,
  createdAt: "2026-01-11T09:30:00.000Z",
};

export const dataWithScenario: ProjectDataResult = {
  projectId: project.id,
  brief: null,
  scenario: scenarioRecord,
  run: null,
};

export const dataWithRun: ProjectDataResult = {
  projectId: project.id,
  brief: null,
  scenario: scenarioRecord,
  run: runRecord,
};
