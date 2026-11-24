import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const ipc = vi.hoisted(() => ({
  ipcAvailable: true,
  getSidecarStatus: vi.fn(),
  getSidecarHealth: vi.fn(),
  listProjects: vi.fn(),
  listTemplates: vi.fn(),
  createProjectFromTemplate: vi.fn(),
  buildReport: vi.fn(),
  getProjectData: vi.fn(),
  agentState: vi.fn(),
  listRoles: vi.fn(),
  onSimulationProgress: vi.fn(),
  simulateProject: vi.fn(),
  startSimulation: vi.fn(),
  cancelSimulation: vi.fn(),
  onSimulationEvent: vi.fn(),
  startSurface: vi.fn(),
  startGoalSeek: vi.fn(),
  cancelAnalysis: vi.fn(),
  onAnalysisEvent: vi.fn(),
  branchProjectScenario: vi.fn(),
  createProject: vi.fn(),
  saveProjectBrief: vi.fn(),
  saveProjectScenario: vi.fn(),
  agentTurn: vi.fn(),
  listAgentPermissions: vi.fn(),
  setAgentPermission: vi.fn(),
  deleteAgentPermission: vi.fn(),
  pingSidecar: vi.fn(),
  restartSidecar: vi.fn(),
}));

vi.mock("./lib/ipc", () => ipc);

import {
  dataWithRun,
  dataWithScenario,
  project,
  runRecord,
  scenarioRecord,
  simulationResult,
} from "./test/fixtures";
import { App } from "./App";

const session = {
  projectId: project.id,
  state: "hypotheses_set" as const,
  role: "interviewer" as const,
  thread: [],
  createdAt: null,
  updatedAt: null,
};

beforeEach(() => {
  vi.resetAllMocks();
  ipc.getSidecarStatus.mockResolvedValue({ running: true, pid: 4321 });
  ipc.getSidecarHealth.mockResolvedValue({
    status: "ok",
    sidecarVersion: "0.1.0",
    protocolVersion: "1.8.0",
    pid: 4321,
    python: "3.11",
  });
  ipc.listProjects.mockResolvedValue({ projects: [project] });
  ipc.listTemplates.mockResolvedValue({ templates: [], errors: [] });
  ipc.getProjectData.mockResolvedValue(dataWithScenario);
  ipc.agentState.mockResolvedValue({ session });
  ipc.listRoles.mockResolvedValue({ assignments: [] });
  ipc.onSimulationProgress.mockResolvedValue(() => undefined);
  ipc.onSimulationEvent.mockResolvedValue(() => undefined);
  ipc.onAnalysisEvent.mockResolvedValue(() => undefined);
  ipc.startSurface.mockResolvedValue({ jobId: "surface-1", accepted: true });
  ipc.startGoalSeek.mockResolvedValue({ jobId: "goal-1", accepted: true });
  ipc.cancelAnalysis.mockResolvedValue(undefined);
  ipc.branchProjectScenario.mockResolvedValue({ scenario: scenarioRecord });
  ipc.startSimulation.mockResolvedValue({ runId: "live-1", accepted: true });
  ipc.cancelSimulation.mockResolvedValue(undefined);
  ipc.simulateProject.mockImplementation(async () => {
    ipc.getProjectData.mockResolvedValue(dataWithRun);
    return { run: runRecord, scenario: scenarioRecord, result: simulationResult };
  });
});

describe("App — parcours critique", () => {
  it("ouvre le scénario puis affiche les résultats après simulation", async () => {
    const user = userEvent.setup();
    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Monte Carlo local" }),
    ).toBeInTheDocument();
    expect(ipc.getProjectData).toHaveBeenCalledWith({ projectId: project.id });

    await user.click(screen.getByRole("button", { name: "Lancer la simulation" }));

    expect(
      await screen.findByRole("heading", { name: "Scénario de base", level: 1 }),
    ).toBeInTheDocument();
    expect(ipc.simulateProject).toHaveBeenCalledWith({
      projectId: project.id,
      config: { runs: 10_000, seed: 42, histogramBins: 40, includeMonthlyHistograms: true },
      progress: true,
    });
    expect(screen.getByText("Distribution du profit")).toBeInTheDocument();
  });

  it("importe le projet d'exemple et affiche le parcours de découverte", async () => {
    const user = userEvent.setup();
    ipc.listTemplates.mockResolvedValue({
      templates: [
        {
          id: "retail-depot-brazzaville",
          name: "Dépôt de revente à Brazzaville",
          description: "Exemple sourcé",
          currency: "XAF",
          sector: "retail",
          horizonMonths: 36,
          seed: 42,
          sources: [{ label: "Enquête locale" }],
          branchCount: 1,
        },
      ],
      errors: [],
    });
    const importedProject = {
      ...project,
      id: "project-demo",
      name: "Dépôt de revente à Brazzaville",
      metadata: { templateId: "retail-depot-brazzaville" },
    };
    ipc.createProjectFromTemplate.mockResolvedValue({
      project: importedProject,
      scenario: scenarioRecord,
      branches: [],
      seed: 42,
      version: {
        id: "version-1",
        projectId: importedProject.id,
        scenarioId: scenarioRecord.id,
        label: "Scénario de départ",
        seed: 42,
        engineVersion: "0.4.0",
        createdAt: "2026-11-23T00:00:00.000Z",
      },
      templateId: "retail-depot-brazzaville",
      importedAt: "2026-11-23T00:00:00.000Z",
    });
    ipc.getProjectData.mockResolvedValue(dataWithScenario);

    render(<App />);

    await screen.findByRole("heading", { name: "Monte Carlo local" });
    await user.click(screen.getByRole("button", { name: "Projets" }));

    const importButton = await screen.findByRole("button", {
      name: "Importer l'exemple",
    });
    await user.click(importButton);

    expect(ipc.createProjectFromTemplate).toHaveBeenCalledWith(
      "retail-depot-brazzaville",
    );
    expect(ipc.getProjectData).toHaveBeenCalledWith({ projectId: "project-demo" });
    expect(
      await screen.findByRole("dialog", { name: "Parcours découverte" }),
    ).toBeInTheDocument();
  });

  it("remonte une erreur de simulation sans quitter l'écran de calcul", async () => {    const user = userEvent.setup();
    ipc.simulateProject.mockRejectedValue(new Error("moteur indisponible"));
    render(<App />);

    await screen.findByRole("heading", { name: "Monte Carlo local" });
    await user.click(screen.getByRole("button", { name: "Lancer la simulation" }));

    expect(await screen.findByText("moteur indisponible")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Monte Carlo local" })).toBeInTheDocument();
  });

  it("confirme avant de recharger un cockpit modifié", async () => {
    const user = userEvent.setup();
    render(<App />);

    await screen.findByRole("heading", { name: "Monte Carlo local" });
    await user.click(screen.getByRole("button", { name: "Lancer la simulation" }));
    await screen.findByRole("heading", { name: "Scénario de base", level: 1 });

    await user.click(screen.getByRole("button", { name: "Cockpit" }));
    const slider = await screen.findByRole("slider", {
      name: "Prix de vente unitaire — mode",
    });
    fireEvent.keyDown(slider, { key: "ArrowRight" });
    expect(await screen.findByText("Modifications non enregistrées")).toBeInTheDocument();

    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const before = ipc.getProjectData.mock.calls.length;
    try {
      await user.click(screen.getByRole("button", { name: "Recharger l'application" }));
      expect(confirm).toHaveBeenCalledTimes(1);
      expect(ipc.getProjectData).toHaveBeenCalledTimes(before);
      // Le cockpit reste affiché : le rechargement a bien été annulé.
      expect(screen.getByRole("button", { name: "Cockpit" })).toHaveClass(
        "app-nav__item--active",
      );

      confirm.mockReturnValue(true);
      await user.click(screen.getByRole("button", { name: "Recharger l'application" }));
      await waitFor(() =>
        expect(ipc.getProjectData.mock.calls.length).toBeGreaterThan(before),
      );
    } finally {
      confirm.mockRestore();
    }
  });
});
