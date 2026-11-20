import type { MonthlyAverage, Scenario, SimulationResult } from "@see/protocol";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const ipc = vi.hoisted(() => ({
  ipcAvailable: true,
  startSimulation: vi.fn(),
  cancelSimulation: vi.fn(),
  onSimulationEvent: vi.fn(),
}));

vi.mock("../lib/ipc", () => ipc);

import type { SimulationEvent } from "../lib/ipc";
import { project, runRecord, scenarioRecord, simulationResult } from "../test/fixtures";
import { CockpitScreen } from "./CockpitScreen";

function month(index: number): MonthlyAverage {
  return {
    index,
    month: ((index - 1) % 12) + 1,
    meanRevenue: 100_000,
    meanProfit: 20_000,
    meanDemand: 500,
    meanUnitsSold: 480,
    meanStockEnd: 100,
    stockoutProbability: 0.05,
    profitP10: 5_000,
    profitP50: 20_000,
    profitP90: 40_000,
    cashP10: 100_000 + index * 1_000,
    cashP50: 200_000 + index * 1_000,
    cashP90: 300_000 + index * 1_000,
    breakEvenProbability: Math.min(1, index / 12),
  };
}

const result: SimulationResult = {
  ...simulationResult,
  runId: "run-1",
  monthly: { values: Array.from({ length: 12 }, (_, index) => month(index + 1)) },
  convergence: { converged: true, stability: 1, maxRelativeChange: 0, stableBlocks: 3 },
};

const run = { ...runRecord, result };

let handler: ((event: SimulationEvent) => void) | null = null;

beforeEach(() => {
  vi.clearAllMocks();
  handler = null;
  ipc.startSimulation.mockResolvedValue({ runId: "live-1", accepted: true });
  ipc.cancelSimulation.mockResolvedValue({ cancelled: true });
  ipc.onSimulationEvent.mockImplementation(
    async (next: (event: SimulationEvent) => void) => {
      handler = next;
      return () => undefined;
    },
  );
});

function renderCockpit(
  withScenario = true,
  options: { onSaveScenario?: (name: string, scenario: Scenario) => Promise<boolean> } = {},
) {
  const onSaveScenario = options.onSaveScenario ?? (async () => true);
  return render(
    <CockpitScreen
      project={project}
      scenario={withScenario ? scenarioRecord : null}
      run={run}
      onBack={() => undefined}
      onOpenHypotheses={() => undefined}
      onSaveScenario={onSaveScenario}
    />,
  );
}

describe("CockpitScreen", () => {
  it("affiche le cockpit avec KPI, éventail et hypothèses", async () => {
    renderCockpit();

    expect(screen.getByText("Scénario de base")).toBeInTheDocument();
    expect(screen.getByText("Convergé")).toBeInTheDocument();
    expect(screen.getByRole("slider", { name: "Prix de vente unitaire — mode" })).toBeInTheDocument();
    expect(screen.getByText("Trésorerie par mois")).toBeInTheDocument();
    expect(screen.getByText(/12 mois \(horizon\)/)).toBeInTheDocument();
    await waitFor(() => expect(ipc.onSimulationEvent).toHaveBeenCalledTimes(1));
  });

  it("propose un état vide sans scénario", () => {
    renderCockpit(false);
    expect(screen.getByText("Rien à simuler")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ouvrir les hypothèses" })).toBeInTheDocument();
  });

  it("épingle le run courant et affiche son fantôme", () => {
    renderCockpit();

    fireEvent.click(screen.getByRole("button", { name: "Épingler le run" }));

    expect(screen.getByRole("button", { name: "Désépingler le run" })).toBeInTheDocument();
    const ghosts = screen.getByRole("list", { name: "Runs épinglés" });
    expect(within(ghosts).getByText(/graine 42/)).toBeInTheDocument();
    expect(screen.queryByText(/Épinglez un run/)).not.toBeInTheDocument();
  });

  it("lance un calcul final sans forcer le nombre de runs du profil", async () => {
    renderCockpit();
    await waitFor(() => expect(ipc.onSimulationEvent).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: "Relancer" }));

    await waitFor(() => expect(ipc.startSimulation).toHaveBeenCalledTimes(1));
    const params = ipc.startSimulation.mock.calls[0][0] as {
      quality: string;
      config?: { runs?: number };
    };
    expect(params.quality).toBe("final");
    expect(params.config?.runs).toBeUndefined();
  });

  it("applique un résultat final reçu du flux", async () => {
    renderCockpit();
    await waitFor(() => expect(ipc.onSimulationEvent).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: "Relancer" }));
    await waitFor(() => expect(ipc.startSimulation).toHaveBeenCalledTimes(1));

    act(() => {
      handler?.({
        method: "simulation.done",
        params: { runId: "live-1", seq: 3, result, persisted: true },
      } as SimulationEvent);
    });

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Épingler le run" })).toBeInTheDocument(),
    );
  });

  it("marque le résultat périmé dès qu'une hypothèse change", () => {
    renderCockpit();

    fireEvent.keyDown(screen.getByRole("slider", { name: "Prix de vente unitaire — mode" }), {
      key: "ArrowRight",
    });

    expect(screen.getByText("Résultat périmé")).toBeInTheDocument();
  });

  it("verrouille un paramètre et désactive ses poignées", () => {
    renderCockpit();

    fireEvent.click(screen.getByRole("button", { name: "Verrouiller Prix de vente unitaire" }));

    const mode = screen.getByRole("slider", { name: "Prix de vente unitaire — mode" });
    expect(mode).toHaveAttribute("aria-disabled", "true");
    expect(
      screen.getByRole("button", { name: "Déverrouiller Prix de vente unitaire" }),
    ).toBeInTheDocument();
  });

  it("bascule l'éventail entre trésorerie et profit", () => {
    renderCockpit();

    const fan = screen.getByRole("region", { name: "Éventail des résultats" });
    fireEvent.click(within(fan).getByRole("tab", { name: "Profit" }));
    expect(screen.getByText("Profit par mois")).toBeInTheDocument();
    expect(
      screen.queryByRole("slider", { name: "Trésorerie minimale" }),
    ).not.toBeInTheDocument();
  });

  it("change de mois sans relancer le moteur", async () => {
    renderCockpit();
    await waitFor(() => expect(ipc.onSimulationEvent).toHaveBeenCalled());
    const calls = ipc.startSimulation.mock.calls.length;

    fireEvent.change(screen.getByRole("slider", { name: "Mois sélectionné" }), {
      target: { value: "9" },
    });

    expect(screen.getByRole("slider", { name: "Mois sélectionné" })).toHaveValue("9");
    const inspector = screen.getByRole("region", {
      name: "Distribution du mois sélectionné",
    });
    expect(within(inspector).getByText("Mois 9")).toBeInTheDocument();
    expect(ipc.startSimulation).toHaveBeenCalledTimes(calls);
  });

  it("conserve les modifications survenues pendant l'enregistrement", async () => {
    let accept: (value: boolean) => void = () => undefined;
    const onSaveScenario = vi.fn(
      () =>
        new Promise<boolean>((resolve) => {
          accept = resolve;
        }),
    );
    renderCockpit(true, { onSaveScenario });

    fireEvent.click(screen.getByRole("button", { name: "Enregistrer le scénario" }));
    await waitFor(() => expect(onSaveScenario).toHaveBeenCalledTimes(1));

    // Modification pendant que l'IPC de sauvegarde est en vol.
    fireEvent.keyDown(screen.getByRole("slider", { name: "Prix de vente unitaire — mode" }), {
      key: "ArrowRight",
    });
    accept(true);

    await waitFor(() =>
      expect(screen.getByText("Modifications non enregistrées")).toBeInTheDocument(),
    );
    expect(screen.getByText(/nouvelles modifications restent à enregistrer/)).toBeInTheDocument();
  });

  it("laisse l'éditeur ouvert quand le sidecar refuse le calcul", async () => {
    renderCockpit();
    await waitFor(() => expect(ipc.onSimulationEvent).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: "Ajouter un événement" }));
    const catalog = screen.getByRole("dialog", { name: "Catalogue d'événements" });
    fireEvent.click(
      within(catalog).getByRole("button", { name: /Hausse du prix fournisseur/ }),
    );

    const block = await screen.findByRole("button", {
      name: /Hausse du prix fournisseur — mois/,
    });
    await waitFor(() => expect(ipc.startSimulation).toHaveBeenCalled());
    act(() => {
      handler?.({
        method: "simulation.done",
        params: { runId: "live-1", seq: 1, result, persisted: false },
      } as SimulationEvent);
    });
    await waitFor(() => expect(block).toBeEnabled());

    fireEvent.doubleClick(block);

    const editor = screen.getByRole("dialog", { name: "Hausse du prix fournisseur" });
    expect(editor).toBeInTheDocument();

    ipc.startSimulation.mockRejectedValueOnce(new Error("refus du moteur"));
    fireEvent.click(within(editor).getByRole("button", { name: "Appliquer et relancer" }));

    expect(await screen.findByText("Refusé par le moteur")).toBeInTheDocument();
    expect(
      screen.getByRole("dialog", { name: "Hausse du prix fournisseur" }),
    ).toBeInTheDocument();
  });

  it("annule et rétablit l'ajout d'un événement", async () => {
    renderCockpit();
    await waitFor(() => expect(ipc.onSimulationEvent).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: "Ajouter un événement" }));
    const catalog = screen.getByRole("dialog", { name: "Catalogue d'événements" });
    fireEvent.click(
      within(catalog).getByRole("button", { name: /Hausse du prix fournisseur/ }),
    );
    await screen.findByRole("button", { name: /Hausse du prix fournisseur — mois/ });

    fireEvent.keyDown(document.body, { key: "z", ctrlKey: true });
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: /Hausse du prix fournisseur — mois/ }),
      ).not.toBeInTheDocument(),
    );

    fireEvent.keyDown(document.body, { key: "y", ctrlKey: true });
    expect(
      await screen.findByRole("button", { name: /Hausse du prix fournisseur — mois/ }),
    ).toBeInTheDocument();
  });
});
