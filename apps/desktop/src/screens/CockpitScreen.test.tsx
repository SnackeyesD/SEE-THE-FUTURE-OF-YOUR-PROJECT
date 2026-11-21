import type { MonthlyAverage, Scenario, SimulationResult } from "@see/protocol";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const ipc = vi.hoisted(() => ({
  ipcAvailable: true,
  startSimulation: vi.fn(),
  cancelSimulation: vi.fn(),
  onSimulationEvent: vi.fn(),
  startSurface: vi.fn(),
  startGoalSeek: vi.fn(),
  cancelAnalysis: vi.fn(),
  onAnalysisEvent: vi.fn(),
  branchProjectScenario: vi.fn(),
}));

vi.mock("../lib/ipc", () => ipc);

import type { AnalysisEvent, SimulationEvent } from "../lib/ipc";
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
  ipc.startSurface.mockResolvedValue({ jobId: "surface-1", accepted: true });
  ipc.startGoalSeek.mockResolvedValue({ jobId: "goal-1", accepted: true });
  ipc.cancelAnalysis.mockResolvedValue(undefined);
  ipc.onAnalysisEvent.mockResolvedValue(() => undefined);
  ipc.branchProjectScenario.mockResolvedValue({ scenario: scenarioRecord });
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

  it("lance une surface avec les axes et la graine du scénario", async () => {
    renderCockpit();

    fireEvent.click(screen.getByRole("button", { name: "Analyse interactive" }));
    const analysis = screen.getByRole("region", { name: "Analyse interactive" });
    fireEvent.click(within(analysis).getByRole("button", { name: "Calculer la surface" }));

    await waitFor(() => expect(ipc.startSurface).toHaveBeenCalledTimes(1));
    expect(ipc.startSurface).toHaveBeenCalledWith(
      expect.objectContaining({
        projectId: project.id,
        scenario: scenarioRecord.scenario,
        axisX: expect.objectContaining({ key: "unit_price" }),
        axisY: expect.objectContaining({ key: "unit_cost" }),
        grid: [12, 12],
        runs: 200,
        seed: 42,
        quality: "draft",
      }),
    );
  });

  it("conserve les axes de la surface après un changement d'onglet", async () => {
    let analysisHandler: ((event: AnalysisEvent) => void) | null = null;
    ipc.onAnalysisEvent.mockImplementation(
      async (_jobId: string, next: (event: AnalysisEvent) => void) => {
        analysisHandler = next;
        return () => undefined;
      },
    );
    renderCockpit();

    fireEvent.click(screen.getByRole("button", { name: "Analyse interactive" }));
    let analysis = screen.getByRole("region", { name: "Analyse interactive" });
    fireEvent.change(within(analysis).getByLabelText("Axe X (colonnes)"), {
      target: { value: "fixed_costs_monthly" },
    });
    fireEvent.change(within(analysis).getByLabelText("Axe Y (lignes)"), {
      target: { value: "demand_mean_monthly" },
    });
    fireEvent.click(within(analysis).getByRole("button", { name: "Calculer la surface" }));
    await waitFor(() => expect(ipc.onAnalysisEvent).toHaveBeenCalled());

    act(() => {
      analysisHandler?.({
        method: "simulation.done",
        params: {
          jobId: "surface-1",
          kind: "surface",
          result: {
            xValues: [100_000, 200_000],
            yValues: [500, 600],
            zP50: [[1, 2], [3, 4]],
            zP10: null,
            zP90: null,
            current: [150_000, 550],
            metric: "profit_p50",
            runs: 200,
            seed: 42,
            grid: [2, 2],
            cost: 800,
            durationMs: 1,
          },
        },
      } as AnalysisEvent);
    });

    fireEvent.click(within(analysis).getByRole("tab", { name: "Recherche d'objectif" }));
    fireEvent.click(within(analysis).getByRole("tab", { name: "Surface 2D" }));
    expect(within(analysis).getByLabelText("Axe X (colonnes)")).toHaveValue(
      "fixed_costs_monthly",
    );
    expect(within(analysis).getByLabelText("Axe Y (lignes)")).toHaveValue(
      "demand_mean_monthly",
    );

    fireEvent.click(screen.getByRole("button", { name: "Analyse interactive" }));
    fireEvent.click(screen.getByRole("button", { name: "Analyse interactive" }));
    analysis = screen.getByRole("region", { name: "Analyse interactive" });
    expect(within(analysis).getByLabelText("Axe X (colonnes)")).toHaveValue(
      "fixed_costs_monthly",
    );
    expect(within(analysis).getByLabelText("Axe Y (lignes)")).toHaveValue(
      "demand_mean_monthly",
    );

    fireEvent.click(screen.getAllByRole("gridcell")[0]);
    await waitFor(() => expect(ipc.startSimulation).toHaveBeenCalledTimes(1));
    const params = ipc.startSimulation.mock.calls[0][0] as { scenario: Scenario };
    expect(params.scenario.assumptions?.fixed_costs_monthly?.value).toBe(100_000);
    expect(params.scenario.assumptions?.demand_mean_monthly?.value).toBe(500);
  });

  it("lance une recherche d'objectif avec le levier sélectionné", async () => {
    renderCockpit();

    fireEvent.click(screen.getByRole("button", { name: "Analyse interactive" }));
    const analysis = screen.getByRole("region", { name: "Analyse interactive" });
    fireEvent.click(within(analysis).getByRole("tab", { name: "Recherche d'objectif" }));
    fireEvent.change(within(analysis).getByLabelText(/^Cible \(FCFA\)/), {
      target: { value: "300000" },
    });
    fireEvent.click(within(analysis).getByRole("button", { name: "Chercher l'objectif" }));

    await waitFor(() => expect(ipc.startGoalSeek).toHaveBeenCalledTimes(1));
    expect(ipc.startGoalSeek).toHaveBeenCalledWith(
      expect.objectContaining({
        projectId: project.id,
        scenario: scenarioRecord.scenario,
        objective: expect.objectContaining({
          metric: "profit_p50",
          comparator: ">=",
          target: 300_000,
        }),
        levers: [expect.objectContaining({ key: "unit_price" })],
        maxEvaluations: 80,
        runs: 500,
        seed: 42,
        confirmQuality: "final",
      }),
    );
  });

  it("exclut les leviers verrouillés de la recherche d'objectif", async () => {
    renderCockpit();

    fireEvent.click(screen.getByRole("button", { name: "Verrouiller Prix de vente unitaire" }));
    fireEvent.click(screen.getByRole("button", { name: "Analyse interactive" }));
    const analysis = screen.getByRole("region", { name: "Analyse interactive" });
    fireEvent.click(within(analysis).getByRole("tab", { name: "Recherche d'objectif" }));

    expect(
      within(analysis).getByRole("checkbox", { name: /Prix de vente unitaire/ }),
    ).toBeDisabled();
    expect(
      within(analysis).getByRole("checkbox", { name: /Coût d'achat unitaire/ }),
    ).toBeChecked();

    fireEvent.change(within(analysis).getByLabelText(/^Cible \(FCFA\)/), {
      target: { value: "300000" },
    });
    fireEvent.click(within(analysis).getByRole("button", { name: "Chercher l'objectif" }));
    expect(within(analysis).queryByText("Formulaire incomplet")).not.toBeInTheDocument();

    await waitFor(() => expect(ipc.startGoalSeek).toHaveBeenCalledTimes(1));
    const params = ipc.startGoalSeek.mock.calls[0][0] as {
      levers: Array<{ key: string }>;
      locked: string[];
    };
    expect(params.levers.map((lever) => lever.key)).toEqual(["unit_cost"]);
    expect(params.locked).toContain("unit_price");
  });

  it("cible une hypothèse depuis le tornado", async () => {
    renderCockpit();

    fireEvent.click(
      screen.getByRole("button", {
        name: /Demande moyenne mensuelle : .*Activer pour cibler l'hypothèse/,
      }),
    );

    const slider = screen.getByRole("slider", {
      name: "Demande moyenne mensuelle — mode",
    });
    await waitFor(() =>
      expect(slider.closest("article")).toHaveAttribute("data-focused", "true"),
    );
  });

  it("applique un objectif comme nouvelle branche et lance le final", async () => {
    let analysisHandler: ((event: AnalysisEvent) => void) | null = null;
    ipc.onAnalysisEvent.mockImplementation(
      async (_jobId: string, next: (event: AnalysisEvent) => void) => {
        analysisHandler = next;
        return () => undefined;
      },
    );
    ipc.branchProjectScenario.mockImplementation(
      async (params: { scenario: Scenario }) => ({
        scenario: { ...scenarioRecord, scenario: params.scenario },
      }),
    );
    renderCockpit();

    fireEvent.click(screen.getByRole("button", { name: "Analyse interactive" }));
    const analysis = screen.getByRole("region", { name: "Analyse interactive" });
    fireEvent.click(within(analysis).getByRole("tab", { name: "Recherche d'objectif" }));
    fireEvent.change(within(analysis).getByLabelText(/^Cible \(FCFA\)/), {
      target: { value: "300000" },
    });
    fireEvent.click(within(analysis).getByRole("button", { name: "Chercher l'objectif" }));
    await waitFor(() => expect(ipc.onAnalysisEvent).toHaveBeenCalled());

    act(() => {
      analysisHandler?.({
        method: "simulation.done",
        params: {
          jobId: "goal-1",
          kind: "goalseek",
          result: {
            feasible: true,
            best: { unit_price: 6_000 },
            achieved: 300_000,
            target: 300_000,
            gap: 0,
            evaluations: 4,
            trace: [],
            budgetExhausted: false,
            message: "Objectif atteint.",
            metric: "profit_p50",
            comparator: ">=",
            quality: "final",
          },
        },
      } as AnalysisEvent);
    });

    const apply = await screen.findByRole("button", {
      name: "Créer une branche et lancer le calcul final",
    });
    fireEvent.click(apply);

    await waitFor(() => expect(ipc.branchProjectScenario).toHaveBeenCalledTimes(1));
    const branchParams = ipc.branchProjectScenario.mock.calls[0][0] as {
      scenarioId: string;
      scenario: Scenario;
    };
    expect(branchParams.scenarioId).toBe(scenarioRecord.id);
    expect(branchParams.scenario.assumptions?.unit_price?.value).toBe(6_000);

    await waitFor(() => expect(ipc.startSimulation).toHaveBeenCalledTimes(1));
    const finalParams = ipc.startSimulation.mock.calls[0][0] as {
      quality: string;
      seed: number;
      scenario: Scenario;
    };
    expect(finalParams.quality).toBe("final");
    expect(finalParams.seed).toBe(42);
    expect(finalParams.scenario.assumptions?.unit_price?.value).toBe(6_000);
  });
});
