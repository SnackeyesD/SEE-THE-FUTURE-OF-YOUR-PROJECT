import { beforeEach, describe, expect, it, vi } from "vitest";

const tauri = vi.hoisted(() => ({
  eventCallback: null as null | ((event: { payload: unknown }) => void),
  unlisten: vi.fn(),
}));

const core = vi.hoisted(() => ({
  invoke: vi.fn(),
  isTauri: vi.fn(() => true),
}));

vi.mock("@tauri-apps/api/core", () => core);
vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn(async (_name: string, callback: (event: { payload: unknown }) => void) => {
    tauri.eventCallback = callback;
    return tauri.unlisten;
  }),
}));

async function loadIpc() {
  vi.resetModules();
  tauri.eventCallback = null;
  return import("./ipc");
}

function emit(event: unknown) {
  expect(tauri.eventCallback).not.toBeNull();
  tauri.eventCallback?.({ payload: event });
}

const tick = () => new Promise((resolve) => setTimeout(resolve, 25));

const progress = (runId: string, fraction: number) => ({
  method: "simulation.progress",
  params: {
    runId,
    completedRuns: Math.round(fraction * 10),
    totalRuns: 10,
    fraction,
    block: 1,
    convergence: {
      converged: false,
      stability: 0,
      maxRelativeChange: 0,
      stableBlocks: 0,
    },
  },
});

const partial = (runId: string, seq: number) => ({
  method: "simulation.partial",
  params: {
    runId,
    seq,
    aggregates: {
      completedRuns: seq * 2,
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
    },
  },
});

const done = (runId: string, seq: number) => ({
  method: "simulation.done",
  params: { runId, seq, result: { runId }, persisted: true },
});

describe("simulation IPC wrapper", () => {
  beforeEach(() => {
    core.invoke.mockReset();
    tauri.unlisten.mockReset();
  });

  it("uses a single listener for every subscriber", async () => {
    const ipc = await loadIpc();
    const first = vi.fn();
    const second = vi.fn();
    await ipc.onSimulationEvent(first);
    await ipc.onSimulationEvent(second);

    const { listen } = await import("@tauri-apps/api/event");
    expect(listen).toHaveBeenCalledTimes(1);
  });

  it("filters stale runs and non-increasing sequence numbers", async () => {
    const ipc = await loadIpc();
    core.invoke.mockResolvedValue({ runId: "run-1", accepted: true });
    const received: string[] = [];
    await ipc.onSimulationEvent((event) => received.push(event.method));

    await ipc.startSimulation({
      projectId: "p1",
      scenario: { name: "Test" } as never,
      quality: "draft",
      seed: 1,
    });

    emit(progress("ancien-run", 0.5));
    emit(progress("run-1", 0.1));
    expect(received).toEqual(["simulation.progress"]);

    emit(partial("run-1", 1));
    await tick();
    expect(received).toEqual(["simulation.progress", "simulation.partial"]);

    emit(partial("run-1", 1));
    await tick();
    expect(received.filter((method) => method === "simulation.partial")).toHaveLength(1);

    emit(partial("run-1", 2));
    await tick();
    expect(received.filter((method) => method === "simulation.partial")).toHaveLength(2);

    emit(done("run-1", 2));
    expect(received.at(-1)).toBe("simulation.done");

    emit(progress("run-1", 0.9));
    emit(partial("run-1", 3));
    await tick();
    expect(received.filter((method) => method === "simulation.done")).toHaveLength(1);
    expect(received.filter((method) => method === "simulation.partial")).toHaveLength(2);
  });

  it("sends the cancellation for the active run", async () => {
    const ipc = await loadIpc();
    core.invoke.mockResolvedValue({ runId: "run-9", accepted: true });
    await ipc.startSimulation({
      projectId: "p1",
      scenario: { name: "Test" } as never,
      quality: "final",
      seed: 2,
    });
    core.invoke.mockResolvedValue({ cancelled: true });

    await ipc.cancelSimulation("run-9");

    expect(core.invoke).toHaveBeenLastCalledWith("simulation_cancel", {
      runId: "run-9",
    });
  });
});
