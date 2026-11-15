import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const ipc = vi.hoisted(() => ({
  ipcAvailable: true,
  getSidecarStatus: vi.fn(),
  getSidecarHealth: vi.fn(),
  listProjects: vi.fn(),
  getProjectData: vi.fn(),
  agentState: vi.fn(),
  listRoles: vi.fn(),
  onSimulationProgress: vi.fn(),
  simulateProject: vi.fn(),
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
  ipc.getProjectData.mockResolvedValue(dataWithScenario);
  ipc.agentState.mockResolvedValue({ session });
  ipc.listRoles.mockResolvedValue({ assignments: [] });
  ipc.onSimulationProgress.mockResolvedValue(() => undefined);
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
      config: { runs: 10_000, seed: 42, histogramBins: 40 },
      progress: true,
    });
    expect(screen.getByText("Distribution du profit")).toBeInTheDocument();
  });

  it("remonte une erreur de simulation sans quitter l'écran de calcul", async () => {
    const user = userEvent.setup();
    ipc.simulateProject.mockRejectedValue(new Error("moteur indisponible"));
    render(<App />);

    await screen.findByRole("heading", { name: "Monte Carlo local" });
    await user.click(screen.getByRole("button", { name: "Lancer la simulation" }));

    expect(await screen.findByText("moteur indisponible")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Monte Carlo local" })).toBeInTheDocument();
  });
});
