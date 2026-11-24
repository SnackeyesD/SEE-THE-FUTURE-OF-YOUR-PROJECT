import type { SimulationStartParams } from "@see/protocol";
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { SimulationEvent } from "../lib/ipc";
import { createCockpitStore } from "../store/cockpitStore";
import { scenarioIsRunnable, useLiveSimulation } from "./useLiveSimulation";

const scenario = {
  schemaVersion: "1.1.0" as const,
  name: "Base",
  model: "retail_depot" as const,
  assumptions: {
    demand: { value: 100 },
    price: { value: 10 },
  },
  events: [],
};

function setup(options: { enabled?: boolean } = {}) {
  const store = createCockpitStore({ projectId: "p1", scenario, seed: 7 });
  let handler: ((event: SimulationEvent) => void) | null = null;
  const unlisten = vi.fn();
  const subscribe = vi.fn(async (next: (event: SimulationEvent) => void) => {
    handler = next;
    return unlisten;
  });
  let counter = 0;
  const start = vi.fn(async (_params: SimulationStartParams) => ({
    runId: `run-${(counter += 1)}`,
    accepted: true,
  }));
  const cancel = vi.fn(async (_runId: string) => undefined);

  const hook = renderHook(() =>
    useLiveSimulation({
      store,
      enabled: options.enabled,
      deps: { start, cancel, subscribe },
    }),
  );

  return {
    store,
    hook,
    start,
    cancel,
    subscribe,
    unlisten,
    emit: (event: SimulationEvent): void => handler?.(event),
    params: (index: number): SimulationStartParams =>
      start.mock.calls[index][0] as SimulationStartParams,
  };
}

async function flush(): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0);
  });
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useLiveSimulation", () => {
  it("lance un draft puis un final, en annulant le run précédent", async () => {
    const ctx = setup();
    await flush();

    act(() => ctx.hook.result.current.invalidate());
    await flush();

    expect(ctx.start).toHaveBeenCalledTimes(1);
    expect(ctx.params(0).quality).toBe("draft");
    expect(ctx.store.getState().session.status).toBe("drafting");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(400);
    });

    expect(ctx.start).toHaveBeenCalledTimes(2);
    expect(ctx.params(1).quality).toBe("final");
    expect(ctx.cancel).toHaveBeenCalledWith("run-1");
    expect(ctx.store.getState().runs["run-1"].status).toBe("cancelled");
    expect(ctx.store.getState().session.status).toBe("finalizing");
  });

  it("limite les drafts à un toutes les 50 ms", async () => {
    const ctx = setup();
    await flush();

    act(() => ctx.hook.result.current.invalidate());
    await flush();
    act(() => ctx.hook.result.current.invalidate());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(49);
    });
    expect(ctx.start).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(ctx.start).toHaveBeenCalledTimes(2);
    expect(ctx.params(1).quality).toBe("draft");
  });

  it("lance des drafts throttlés pendant un geste et un seul final au relâchement", async () => {
    const ctx = setup();
    await flush();

    act(() => ctx.hook.result.current.beginGesture());
    act(() => ctx.hook.result.current.invalidate());
    await flush();
    expect(ctx.start).toHaveBeenCalledTimes(1);
    expect(ctx.params(0).quality).toBe("draft");

    act(() => ctx.hook.result.current.invalidate());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(250);
    });
    expect(ctx.start).toHaveBeenCalledTimes(2);
    expect(ctx.params(1).quality).toBe("draft");
    // Aucun final automatique tant que le geste n'est pas relâché.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(400);
    });
    expect(ctx.start).toHaveBeenCalledTimes(2);

    act(() => ctx.hook.result.current.endGesture());
    await flush();

    expect(ctx.start).toHaveBeenCalledTimes(3);
    expect(ctx.params(2).quality).toBe("final");
    expect(ctx.store.getState().runs["run-2"].status).toBe("cancelled");
  });

  it("ne relance pas un geste qui n'a rien changé", async () => {
    const ctx = setup();
    await flush();

    act(() => ctx.hook.result.current.beginGesture());
    act(() => ctx.hook.result.current.endGesture());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });

    expect(ctx.start).not.toHaveBeenCalled();
  });

  it("n'émet aucun run après démontage", async () => {
    const ctx = setup();
    await flush();

    act(() => ctx.hook.result.current.invalidate());
    await flush();
    expect(ctx.start).toHaveBeenCalledTimes(1);
    expect(ctx.params(0).quality).toBe("draft");

    ctx.hook.unmount();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1_000);
    });

    expect(ctx.start).toHaveBeenCalledTimes(1);
  });

  it("applique les événements du run actif et ignore les périmés", async () => {
    const ctx = setup();
    await flush();

    act(() => {
      void ctx.hook.result.current.runFinal();
    });
    await flush();
    expect(ctx.store.getState().session.activeRunId).toBe("run-1");

    const aggregates = (completedRuns: number) => ({
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
    });
    const emitRaw = (event: unknown): void => {
      act(() => ctx.emit(event as SimulationEvent));
    };

    emitRaw({
      method: "simulation.partial",
      params: { runId: "autre", seq: 1, aggregates: aggregates(1) },
    });
    expect(ctx.store.getState().runs["run-1"].aggregates).toBeNull();

    emitRaw({
      method: "simulation.partial",
      params: { runId: "run-1", seq: 1, aggregates: aggregates(3) },
    });
    expect(ctx.store.getState().runs["run-1"].aggregates?.completedRuns).toBe(3);

    emitRaw({
      method: "simulation.partial",
      params: { runId: "run-1", seq: 1, aggregates: aggregates(9) },
    });
    expect(ctx.store.getState().runs["run-1"].aggregates?.completedRuns).toBe(3);

    emitRaw({
      method: "simulation.done",
      params: {
        runId: "run-1",
        seq: 2,
        result: { engineVersion: "0.3.0" },
        persisted: false,
      },
    });
    expect(ctx.store.getState().session.status).toBe("idle");
    expect(ctx.store.getState().runs["run-1"].status).toBe("done");
    expect(ctx.store.getState().runs["run-1"].engineVersion).toBe("0.3.0");
  });

  it("remonte une erreur de démarrage sans perdre la main", async () => {
    const ctx = setup();
    await flush();
    ctx.start.mockRejectedValueOnce(new Error("moteur indisponible"));

    act(() => {
      void ctx.hook.result.current.runFinal();
    });
    await flush();

    expect(ctx.store.getState().session.status).toBe("error");
    expect(ctx.store.getState().session.error).toBe("moteur indisponible");
  });

  it("ne lance aucun calcul quand le contrôleur est désactivé", async () => {
    const ctx = setup({ enabled: false });
    await flush();

    act(() => ctx.hook.result.current.invalidate());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(400);
    });

    expect(ctx.start).not.toHaveBeenCalled();
  });

  it("annule le run actif et se désabonne au démontage", async () => {
    const ctx = setup();
    await flush();
    act(() => {
      void ctx.hook.result.current.runFinal();
    });
    await flush();
    expect(ctx.store.getState().session.activeRunId).toBe("run-1");

    ctx.hook.unmount();
    await flush();

    expect(ctx.cancel).toHaveBeenCalledWith("run-1");
    expect(ctx.unlisten).toHaveBeenCalled();
    expect(ctx.store.getState().session.activeRunId).toBeNull();
  });
});

describe("scenarioIsRunnable", () => {
  it("refuse un scénario sans nom ou sans hypothèse exploitable", () => {
    expect(scenarioIsRunnable(null)).toBe(false);
    expect(scenarioIsRunnable({ name: "  " })).toBe(false);
    expect(scenarioIsRunnable({ name: "Vide", assumptions: {} })).toBe(false);
    expect(
      scenarioIsRunnable({ name: "NaN", assumptions: { a: { value: Number.NaN } } }),
    ).toBe(false);
    expect(scenarioIsRunnable(scenario)).toBe(true);
  });
});
