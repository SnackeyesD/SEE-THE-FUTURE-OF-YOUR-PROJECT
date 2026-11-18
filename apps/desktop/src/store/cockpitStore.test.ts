import type {
  PartialAggregates,
  Scenario,
  SimulationResult,
} from "@see/protocol";
import { describe, expect, it } from "vitest";

import {
  createCockpitStore,
  selectActiveRun,
  selectPinnedRuns,
} from "./cockpitStore";

const scenario: Scenario = {
  schemaVersion: "1.1.0",
  name: "Base",
  model: "retail_depot",
  assumptions: {
    demand: { value: 100 },
    price: { value: 10 },
  },
  events: [],
};

function makeResult(engineVersion = "0.3.0"): SimulationResult {
  return {
    runId: "run",
    engineVersion,
    scenarioName: "Base",
    model: "retail_depot",
    currency: "XOF",
    horizonMonths: 12,
    runs: 10,
    seed: 7,
    durationMs: 1,
    metrics: {},
    histogram: {},
    monthly: {},
    sensitivity: [],
    breakEven: {},
  } as unknown as SimulationResult;
}

function makePartial(completedRuns = 5): PartialAggregates {
  return {
    completedRuns,
    totalRuns: 10,
    metrics: {},
    histogram: {},
    monthly: {},
    convergence: {
      converged: false,
      stability: 0,
      maxRelativeChange: 0,
      stableBlocks: 0,
    },
  } as unknown as PartialAggregates;
}

function createStore() {
  return createCockpitStore({ projectId: "p1", scenario, seed: 7 });
}

describe("cockpitStore — entrées", () => {
  it("met à jour une hypothèse sans muter le scénario précédent", () => {
    const store = createStore();
    const before = store.getState().session.scenario;

    store.getState().setParam("demand", { value: 250 });

    expect(store.getState().session.scenario.assumptions?.demand.value).toBe(250);
    expect(before.assumptions?.demand.value).toBe(100);
  });

  it("ajoute, modifie et supprime un événement", () => {
    const store = createStore();
    store.getState().addEvent({
      id: "event-1",
      type: "demand_peak",
      startMonth: 3,
      durationMonths: 2,
      target: "demand",
      magnitude: { kind: "uniform", low: 1, high: 2 },
    });
    store.getState().updateEvent("event-1", { startMonth: 5 });
    expect(store.getState().session.scenario.events?.[0].startMonth).toBe(5);

    store.getState().removeEvent("event-1");
    expect(store.getState().session.scenario.events).toEqual([]);
  });

  it("marque les résultats non épinglés comme périmés", () => {
    const store = createStore();
    store.getState().startRun({ runId: "r1", quality: "final", seed: 7 });
    store.getState().applyFinal({ runId: "r1", seq: 2, result: makeResult() });
    store.getState().startRun({ runId: "r2", quality: "final", seed: 7 });
    store.getState().applyFinal({ runId: "r2", seq: 2, result: makeResult() });
    store.getState().pinRun("r2");

    store.getState().setSeed(9);

    expect(store.getState().runs.r1.stale).toBe(true);
    expect(store.getState().runs.r2.stale).toBe(false);
    expect(store.getState().session.seed).toBe(9);
  });
});

describe("cockpitStore — runs", () => {
  it("démarre un run et applique les partiels dans l'ordre", () => {
    const store = createStore();
    store.getState().startRun({ runId: "r1", quality: "draft", seed: 7 });

    store.getState().applyPartial({ runId: "r1", seq: 2, aggregates: makePartial(4) });
    store.getState().applyPartial({ runId: "r1", seq: 1, aggregates: makePartial(1) });
    store.getState().applyPartial({ runId: "autre", seq: 9, aggregates: makePartial(9) });

    const run = store.getState().runs.r1;
    expect(run.seq).toBe(2);
    expect(run.aggregates?.completedRuns).toBe(4);
    expect(store.getState().session.lastSeq).toBe(2);
    expect(store.getState().session.status).toBe("drafting");
  });

  it("termine le run actif et ignore les résultats périmés", () => {
    const store = createStore();
    store.getState().startRun({ runId: "r1", quality: "final", seed: 7 });
    store.getState().applyPartial({ runId: "r1", seq: 5, aggregates: makePartial() });

    store.getState().applyFinal({ runId: "r1", seq: 4, result: makeResult() });
    expect(store.getState().session.status).toBe("finalizing");

    store.getState().applyFinal({ runId: "r1", seq: 6, result: makeResult("0.4.0") });
    expect(store.getState().session.status).toBe("idle");
    expect(store.getState().session.activeRunId).toBeNull();
    expect(store.getState().runs.r1.status).toBe("done");
    expect(store.getState().runs.r1.engineVersion).toBe("0.4.0");

    store.getState().applyFinal({ runId: "autre", seq: 7, result: makeResult() });
    expect(store.getState().runs.r1.seq).toBe(6);
  });

  it("conserve le dernier résultat valide quand un run échoue", () => {
    const store = createStore();
    store.getState().startRun({ runId: "r1", quality: "final", seed: 7 });
    store.getState().applyFinal({ runId: "r1", seq: 1, result: makeResult() });
    store.getState().startRun({ runId: "r2", quality: "final", seed: 7 });

    store.getState().failRun("r2", { code: "simulation_failed", message: "moteur cassé" });

    expect(store.getState().session.status).toBe("error");
    expect(store.getState().session.error).toBe("moteur cassé");
    expect(store.getState().runs.r2.status).toBe("error");
    expect(store.getState().runs.r1.result).not.toBeNull();
  });

  it("annule le run actif sans toucher aux autres", () => {
    const store = createStore();
    store.getState().startRun({ runId: "r1", quality: "draft", seed: 7 });
    store.getState().cancelRun("r1");

    expect(store.getState().session.status).toBe("idle");
    expect(store.getState().session.activeRunId).toBeNull();
    expect(store.getState().runs.r1.status).toBe("cancelled");
  });

  it("n'épingle que les runs terminés", () => {
    const store = createStore();
    store.getState().startRun({ runId: "r1", quality: "final", seed: 7 });
    store.getState().pinRun("r1");
    expect(store.getState().pinned).toEqual([]);

    store.getState().applyFinal({ runId: "r1", seq: 1, result: makeResult() });
    store.getState().pinRun("r1");
    expect(store.getState().pinned).toEqual(["r1"]);

    store.getState().pinRun("r1", false);
    expect(store.getState().pinned).toEqual([]);
  });

  it("expose des sélecteurs pour le run actif et les épinglés", () => {
    const store = createStore();
    store.getState().startRun({ runId: "r1", quality: "final", seed: 7 });
    store.getState().applyFinal({ runId: "r1", seq: 1, result: makeResult() });
    store.getState().pinRun("r1");
    store.getState().startRun({ runId: "r2", quality: "final", seed: 7 });

    expect(selectActiveRun(store.getState())?.runId).toBe("r2");
    expect(selectPinnedRuns(store.getState()).map((run) => run.runId)).toEqual(["r1"]);
  });

  it("réinitialise la session et la pile de runs", () => {
    const store = createStore();
    store.getState().setSeed(99);
    store.getState().startRun({ runId: "r1", quality: "final", seed: 99 });
    store.getState().pinRun("r1");

    store.getState().reset();

    expect(store.getState().runs).toEqual({});
    expect(store.getState().pinned).toEqual([]);
    expect(store.getState().session.seed).toBe(7);
    expect(store.getState().session.scenario.name).toBe("Base");
  });
});
