import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { SurfaceState } from "../../hooks/useAnalysis";
import type { WebGLStatus } from "../../lib/webgl";
import { scenario } from "../../test/fixtures";
import { SurfacePanel } from "./SurfacePanel";

const webgl = vi.hoisted(() => ({
  detectWebGL: vi.fn<() => WebGLStatus>(() => ({ supported: true })),
}));

vi.mock("../../lib/webgl", () => ({
  detectWebGL: webgl.detectWebGL,
}));

vi.mock("./Surface3DView", () => ({
  Surface3DView: (props: {
    onPick: (x: number, y: number) => void;
    onFallback: (reason: string) => void;
  }) => (
    <div data-testid="surface3d">
      <button type="button" onClick={() => props.onPick(20, 200)}>
        Choisir un point 3D
      </button>
      <button type="button" onClick={() => props.onFallback("context_lost")}>
        Simuler une perte de contexte
      </button>
    </div>
  ),
}));

const state: SurfaceState = {
  jobId: "job-1",
  status: "done",
  fraction: 1,
  completedPoints: 4,
  totalPoints: 4,
  rows: [
    [1, 2],
    [3, 4],
  ],
  result: {
    xValues: [10, 20],
    yValues: [100, 200],
    zP50: [
      [1, 2],
      [3, 4],
    ],
    current: [20, 100],
    metric: "profit_p50",
    runs: 20,
    seed: 42,
    grid: [2, 2],
    cost: 80,
    durationMs: 12,
  },
  error: null,
  replacedJobId: null,
};

function setup(overrides: { state?: SurfaceState } = {}) {
  const onApplyPoint = vi.fn();
  const view = render(
    <SurfacePanel
      scenario={scenario}
      projectId="project-1"
      currency="XOF"
      state={overrides.state ?? state}
      seed={42}
      finalRunId="run-1"
      onRun={vi.fn()}
      onCancel={vi.fn()}
      onApplyPoint={onApplyPoint}
    />,
  );
  return { onApplyPoint, ...view };
}

beforeEach(() => {
  window.localStorage.clear();
  webgl.detectWebGL.mockReset();
  webgl.detectWebGL.mockReturnValue({ supported: true });
});

describe("SurfacePanel — vue 3D et repli", () => {
  it("reste en carte 2D par défaut", () => {
    setup();
    expect(screen.getByRole("grid").getAttribute("aria-label")).toContain("Profit médian");
    expect(screen.getByRole("button", { name: "Carte 2D" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.queryByTestId("surface3d")).toBeNull();
  });

  it("bascule en 3D, mémorise la préférence et applique un point", () => {
    const { onApplyPoint } = setup();
    fireEvent.click(screen.getByRole("button", { name: "Vue 3D" }));

    expect(screen.getByTestId("surface3d")).toBeTruthy();
    expect(window.localStorage.getItem("see.surface.view.project-1")).toBe("3d");

    fireEvent.click(screen.getByRole("button", { name: "Choisir un point 3D" }));
    expect(onApplyPoint).toHaveBeenCalledWith({ unit_price: 20, unit_cost: 200 });
  });

  it("replie sans WebGL et conserve la heatmap", () => {
    webgl.detectWebGL.mockReturnValue({ supported: false, reason: "no_context" });
    setup();
    fireEvent.click(screen.getByRole("button", { name: "Vue 3D" }));

    expect(screen.queryByTestId("surface3d")).toBeNull();
    expect(screen.getByText(/WebGL n'est pas disponible/)).toBeTruthy();
    expect(screen.getByRole("grid")).toBeTruthy();
    expect(window.localStorage.getItem("see.surface.view.project-1")).toBe("2d");
  });

  it("replie immédiatement sur une perte de contexte", () => {
    setup();
    fireEvent.click(screen.getByRole("button", { name: "Vue 3D" }));
    fireEvent.click(screen.getByRole("button", { name: "Simuler une perte de contexte" }));

    expect(screen.queryByTestId("surface3d")).toBeNull();
    expect(screen.getByText(/contexte WebGL a été perdu/)).toBeTruthy();
    expect(screen.getByRole("grid")).toBeTruthy();
  });

  it("respecte une préférence 3D déjà enregistrée", () => {
    window.localStorage.setItem("see.surface.view.project-1", "3d");
    setup();
    expect(screen.getByTestId("surface3d")).toBeTruthy();
  });

  it("désactive la 3D tant que le calcul n'est pas terminé", () => {
    setup({ state: { ...state, result: null, status: "running", rows: [[1, 2]] } });
    expect(screen.getByRole("button", { name: "Vue 3D" })).toBeDisabled();
  });
});
