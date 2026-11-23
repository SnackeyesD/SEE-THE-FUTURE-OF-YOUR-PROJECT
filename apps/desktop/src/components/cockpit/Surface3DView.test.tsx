import type { SimulationTrajectoriesResult } from "@see/protocol";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { WebGLStatus } from "../../lib/webgl";
import { Surface3DView } from "./Surface3DView";

const webgl = vi.hoisted(() => ({
  detectWebGL: vi.fn<() => WebGLStatus>(() => ({ supported: true })),
}));

const ipc = vi.hoisted(() => ({
  getTrajectories: vi.fn(),
  getRunParams: vi.fn(),
}));

vi.mock("../../lib/webgl", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../lib/webgl")>();
  return { ...actual, detectWebGL: webgl.detectWebGL };
});

vi.mock("../../lib/ipc", () => ({
  getTrajectories: ipc.getTrajectories,
  getRunParams: ipc.getRunParams,
}));

vi.mock("./Scene3D", () => ({
  default: (props: {
    onContextLost: () => void;
    onPickCell: (column: number, row: number) => void;
  }) => (
    <div data-testid="scene3d">
      <button type="button" onClick={props.onContextLost}>
        Perdre le contexte
      </button>
      <button type="button" onClick={() => props.onPickCell(1, 1)}>
        Cliquer la cellule 1,1
      </button>
    </div>
  ),
}));

const trajectories: SimulationTrajectoriesResult = {
  runId: "run-1",
  seed: 42,
  engineVersion: "0.4.0",
  runs: 100,
  runsRetained: 2,
  horizonMonths: 2,
  currency: "XOF",
  truncated: true,
  trajectories: [
    {
      index: 0,
      profitMonthly: [10, 10],
      cashMonthly: [-20, 10],
      revenueMonthly: [100, 100],
    },
    {
      index: 1,
      profitMonthly: [-5, -5],
      cashMonthly: [10, 0],
      revenueMonthly: [50, 50],
    },
  ],
};

function setup(overrides: { runId?: string | null } = {}) {
  const onFallback = vi.fn();
  const onPick = vi.fn();
  const view = render(
    <Surface3DView
      runId={overrides.runId === undefined ? "run-1" : overrides.runId}
      xValues={[10, 20]}
      yValues={[100, 200]}
      z={[
        [1, 2],
        [3, 4],
      ]}
      current={[20, 100]}
      metric="profit_p50"
      xLabel="Prix"
      yLabel="Coût"
      currency="XOF"
      onPick={onPick}
      onFallback={onFallback}
    />,
  );
  return { onFallback, onPick, ...view };
}

beforeEach(() => {
  ipc.getTrajectories.mockReset();
  ipc.getRunParams.mockReset();
  ipc.getTrajectories.mockResolvedValue(trajectories);
  webgl.detectWebGL.mockReset();
  webgl.detectWebGL.mockReturnValue({ supported: true });
});

describe("Surface3DView", () => {
  it("replie et explique quand WebGL est absent", () => {
    webgl.detectWebGL.mockReturnValue({ supported: false, reason: "no_context" });
    const { onFallback } = setup();

    expect(screen.getByText(/WebGL n'est pas disponible/)).toBeTruthy();
    expect(onFallback).toHaveBeenCalledWith("no_context");
    expect(screen.queryByTestId("scene3d")).toBeNull();
  });

  it("désactive le nuage sans run final et propose le retour 2D", () => {
    const { onFallback } = setup({ runId: null });

    expect(screen.getByRole("button", { name: "Nuage Monte Carlo" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Revenir à la carte 2D" }));
    expect(onFallback).toHaveBeenCalledWith("slow");
  });

  it("charge les trajectoires à l'ouverture du nuage", async () => {
    setup();
    fireEvent.click(screen.getByRole("button", { name: "Nuage Monte Carlo" }));

    await waitFor(() =>
      expect(ipc.getTrajectories).toHaveBeenCalledWith({ runId: "run-1", count: 200 }),
    );
    expect(await screen.findByText(/2 trajectoire\(s\)/)).toBeTruthy();
    expect(screen.getByText(/Échantillon borné à 2 trajectoires/)).toBeTruthy();
  });

  it("remonte la perte de contexte au parent", () => {
    const { onFallback } = setup();
    fireEvent.click(screen.getByRole("button", { name: "Perdre le contexte" }));
    expect(onFallback).toHaveBeenCalledWith("context_lost");
  });

  it("applique une cellule au scénario via les deux axes", () => {
    const { onPick } = setup();
    fireEvent.click(screen.getByRole("button", { name: "Cliquer la cellule 1,1" }));
    expect(onPick).toHaveBeenCalledWith(20, 200);
  });
});
