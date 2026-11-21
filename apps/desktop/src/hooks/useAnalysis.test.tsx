import type { GoalSeekResult, Scenario, SurfaceResult } from "@see/protocol";
import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { AnalysisEvent } from "../lib/ipc";
import { useAnalysis } from "./useAnalysis";

const scenario: Scenario = {
  schemaVersion: "1.1.0",
  name: "Base",
  model: "retail_depot",
  currency: "XOF",
  horizonMonths: 12,
  assumptions: {
    unit_price: { value: 5_000 },
    unit_cost: { value: 3_000 },
  },
};

function setup() {
  const handlers = new Map<string, (event: AnalysisEvent) => void>();
  const startSurface = vi.fn(async () => ({ jobId: "surface-1", accepted: true }));
  const startGoalSeek = vi.fn(async () => ({ jobId: "goal-1", accepted: true }));
  const cancel = vi.fn(async (_jobId: string) => undefined);
  const subscribe = vi.fn(async (jobId: string, next: (event: AnalysisEvent) => void) => {
    handlers.set(jobId, next);
    return () => {
      handlers.delete(jobId);
    };
  });
  const hook = renderHook(() =>
    useAnalysis({ deps: { startSurface, startGoalSeek, cancel, subscribe } }),
  );

  return {
    hook,
    startSurface,
    startGoalSeek,
    cancel,
    subscribe,
    emit: (event: AnalysisEvent): void => {
      act(() => handlers.get(event.params.jobId)?.(event));
    },
  };
}

const surfaceResult: SurfaceResult = {
  xValues: [0, 1],
  yValues: [10, 20],
  zP50: [[1, 2], [3, 4]],
  zP10: null,
  zP90: null,
  current: [0.5, 15],
  metric: "profit_p50",
  runs: 10,
  seed: 7,
  grid: [2, 2],
  cost: 40,
  durationMs: 12,
};

describe("useAnalysis", () => {
  it("assemble les lignes partielles puis le résultat final de la surface", async () => {
    const ctx = setup();

    await act(async () => {
      await ctx.hook.result.current.runSurface({
        projectId: "p1",
        scenario,
        axisX: { key: "unit_price", minimum: 0, maximum: 1 },
        axisY: { key: "unit_cost", minimum: 10, maximum: 20 },
        metric: "profit_p50",
        grid: [2, 2],
        runs: 10,
        seed: 7,
      });
    });

    expect(ctx.hook.result.current.surface.status).toBe("running");
    expect(ctx.hook.result.current.surface.rows).toEqual([
      [null, null],
      [null, null],
    ]);

    ctx.emit({
      method: "simulation.surface.partial",
      params: {
        jobId: "surface-1",
        seq: 1,
        rowIndex: 1,
        values: [3, 4],
        completedPoints: 3,
        totalPoints: 4,
      },
    });
    expect(ctx.hook.result.current.surface.rows[1]).toEqual([3, 4]);
    expect(ctx.hook.result.current.surface.completedPoints).toBe(3);

    ctx.emit({
      method: "simulation.done",
      params: { jobId: "surface-1", kind: "surface", result: surfaceResult },
    });
    expect(ctx.hook.result.current.surface.status).toBe("done");
    expect(ctx.hook.result.current.surface.rows).toEqual(surfaceResult.zP50);
    expect(ctx.hook.result.current.surface.fraction).toBe(1);
    ctx.hook.unmount();
  });

  it("annule une surface et conserve le motif de l'annulation", async () => {
    const ctx = setup();
    await act(async () => {
      await ctx.hook.result.current.runSurface({
        projectId: "p1",
        scenario,
        axisX: { key: "unit_price", minimum: 0, maximum: 1 },
        axisY: { key: "unit_cost", minimum: 10, maximum: 20 },
      });
    });

    act(() => ctx.hook.result.current.cancelSurface());
    expect(ctx.cancel).toHaveBeenCalledWith("surface-1");
    expect(ctx.hook.result.current.surface.status).toBe("cancelling");

    ctx.emit({
      method: "simulation.cancelled",
      params: { jobId: "surface-1", kind: "surface", reason: "analysis_cancelled" },
    });
    expect(ctx.hook.result.current.surface.status).toBe("cancelled");
    expect(ctx.hook.result.current.surface.error).toBe("Analyse annulée.");
    ctx.hook.unmount();
  });

  it("annule une surface pendant l'attente de l'accusé de démarrage", async () => {
    let accept: (value: { jobId: string; accepted: boolean }) => void = () => undefined;
    const startSurface = vi.fn(
      () =>
        new Promise<{ jobId: string; accepted: boolean }>((resolve) => {
          accept = resolve;
        }),
    );
    const startGoalSeek = vi.fn();
    const cancel = vi.fn(async (_jobId: string) => undefined);
    const subscribe = vi.fn();
    const hook = renderHook(() =>
      useAnalysis({ deps: { startSurface, startGoalSeek, cancel, subscribe } }),
    );

    let request: Promise<boolean> | null = null;
    act(() => {
      request = hook.result.current.runSurface({
        projectId: "p1",
        scenario,
        axisX: { key: "unit_price", minimum: 0, maximum: 1 },
        axisY: { key: "unit_cost", minimum: 10, maximum: 20 },
      });
    });
    expect(hook.result.current.surface.status).toBe("running");

    act(() => hook.result.current.cancelSurface());
    expect(hook.result.current.surface.status).toBe("cancelling");

    await act(async () => {
      accept({ jobId: "surface-1", accepted: true });
      expect(await request).toBe(false);
    });
    expect(cancel).toHaveBeenCalledWith("surface-1");
    expect(subscribe).not.toHaveBeenCalled();
    expect(hook.result.current.surface.status).toBe("cancelled");
    hook.unmount();
  });

  it("applique le résultat de la recherche et ignore un ancien job", async () => {
    const ctx = setup();
    await act(async () => {
      await ctx.hook.result.current.runGoalSeek({
        projectId: "p1",
        scenario,
        objective: { metric: "profit_p50", comparator: ">=", target: 300_000 },
        levers: [{ key: "unit_price", minimum: 0, maximum: 10_000 }],
        maxEvaluations: 5,
      });
    });

    const result: GoalSeekResult = {
      feasible: false,
      best: { unit_price: 6_000 },
      achieved: 250_000,
      target: 300_000,
      gap: -50_000,
      evaluations: 5,
      trace: [],
      budgetExhausted: true,
      message: "Budget épuisé.",
      metric: "profit_p50",
      comparator: ">=",
      quality: "draft",
    };
    ctx.emit({
      method: "simulation.done",
      params: { jobId: "autre-job", kind: "goalseek", result },
    });
    expect(ctx.hook.result.current.goal.result).toBeNull();

    ctx.emit({
      method: "simulation.done",
      params: { jobId: "goal-1", kind: "goalseek", result },
    });
    expect(ctx.hook.result.current.goal.status).toBe("done");
    expect(ctx.hook.result.current.goal.result).toEqual(result);
    ctx.hook.unmount();
  });
});
