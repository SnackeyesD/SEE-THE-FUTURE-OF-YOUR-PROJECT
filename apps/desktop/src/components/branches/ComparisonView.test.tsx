import type { ProjectRunCompareResult, RunRef } from "@see/protocol";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { simulationResult } from "../../test/fixtures";
import { ComparisonView } from "./ComparisonView";

function run(overrides: Partial<RunRef> = {}): RunRef {
  return {
    id: "run-a",
    scenarioId: "scenario-a",
    seed: 42,
    engineVersion: "0.4.0",
    runs: 5_000,
    pinned: false,
    createdAt: "2026-01-10T08:05:00.000Z",
    summary: {},
    ...overrides,
  };
}

function comparison(overrides: Partial<ProjectRunCompareResult> = {}): ProjectRunCompareResult {
  return {
    sameSeed: true,
    sameEngineVersion: true,
    runs: [
      {
        id: "run-a",
        scenarioId: "scenario-a",
        seed: 42,
        engineVersion: "0.4.0",
        result: simulationResult,
      },
      {
        id: "run-b",
        scenarioId: "scenario-b",
        seed: 42,
        engineVersion: "0.4.0",
        result: {
          ...simulationResult,
          metrics: {
            ...simulationResult.metrics,
            p50: 260_000,
            breakEvenProbability: 0.85,
          },
        },
      },
    ],
    ...overrides,
  };
}

function setup(overrides: {
  runs?: RunRef[];
  runIds?: [string | null, string | null];
  comparison?: ProjectRunCompareResult | null;
} = {}) {
  const actions = { onSelect: vi.fn(), onPin: vi.fn() };
  const view = render(
    <ComparisonView
      runs={overrides.runs ?? [run(), run({ id: "run-b", scenarioId: "scenario-b" })]}
      runIds={overrides.runIds ?? ["run-a", "run-b"]}
      comparison={overrides.comparison ?? comparison()}
      currency="XOF"
      {...actions}
    />,
  );
  return { actions, ...view };
}

describe("ComparisonView", () => {
  it("affiche un état vide sans run final", () => {
    setup({ runs: [], comparison: null });
    expect(screen.getByText("Aucun run final à comparer")).toBeTruthy();
  });

  it("affiche les deux runs, les métriques et les deltas", () => {
    setup();
    expect(screen.getByText("graine identique")).toBeTruthy();
    expect(screen.getByText("même version de moteur")).toBeTruthy();
    expect(screen.getByText("Profit P50")).toBeTruthy();
    expect(screen.getByText("+20 000 F CFA")).toBeTruthy();
    expect(screen.getByText(/\+8,3/)).toBeTruthy();
  });

  it("avertit explicitement quand les graines diffèrent", () => {
    setup({
      comparison: comparison({
        sameSeed: false,
        runs: [
          { ...comparison().runs[0], seed: 42 },
          { ...comparison().runs[1], seed: 43 },
        ],
      }),
    });
    expect(screen.getByText("Graines différentes")).toBeTruthy();
    expect(screen.getByText(/Un écart de graine est du bruit/)).toBeTruthy();
    expect(screen.getByText("graine différente")).toBeTruthy();
  });

  it("avertit quand la version de moteur diffère", () => {
    setup({
      comparison: comparison({
        sameEngineVersion: false,
        runs: [
          comparison().runs[0],
          { ...comparison().runs[1], engineVersion: "0.5.0" },
        ],
      }),
    });
    expect(screen.getByText("Versions de moteur différentes")).toBeTruthy();
    expect(screen.getByText(/Recalculez avec la version courante/)).toBeTruthy();
  });

  it("propose épingler ou désépingler le run sélectionné", () => {
    const { actions } = setup({
      runs: [run({ id: "run-a", pinned: true }), run({ id: "run-b" })],
    });
    fireEvent.click(screen.getByRole("button", { name: "Désépingler" }));
    expect(actions.onPin).toHaveBeenCalledWith(
      expect.objectContaining({ id: "run-a" }),
      false,
    );
  });

  it("change la sélection d'un côté", () => {
    const { actions } = setup();
    fireEvent.change(screen.getByLabelText("Sélection du run B"), {
      target: { value: "run-a" },
    });
    expect(actions.onSelect).toHaveBeenCalledWith(1, "run-a");
  });
});
