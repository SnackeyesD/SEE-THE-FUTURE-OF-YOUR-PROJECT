import type {
  BranchRef,
  ProjectRunCompareResult,
  RunRef,
  Scenario,
  ScenarioRecord,
} from "@see/protocol";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const ipc = vi.hoisted(() => ({
  listBranches: vi.fn(),
  getScenario: vi.fn(),
  listVersions: vi.fn(),
  listRuns: vi.fn(),
  compareRuns: vi.fn(),
  branchProjectScenario: vi.fn(),
  renameScenario: vi.fn(),
  archiveScenario: vi.fn(),
  unarchiveScenario: vi.fn(),
  createVersion: vi.fn(),
  restoreVersion: vi.fn(),
  deleteVersion: vi.fn(),
  pinRun: vi.fn(),
}));

vi.mock("../lib/ipc", () => ipc);

import { project, scenario, scenarioRecord, simulationResult } from "../test/fixtures";
import { BranchesScreen } from "./BranchesScreen";

const scenarioA: Scenario = {
  ...scenario,
  name: "Base",
  assumptions: {
    ...scenario.assumptions,
    unit_price: { value: 5_000 },
  },
};

const scenarioB: Scenario = {
  ...scenario,
  name: "Variante",
  assumptions: {
    ...scenario.assumptions,
    unit_price: { value: 5_500 },
  },
};

function branch(overrides: Partial<BranchRef> = {}): BranchRef {
  return {
    scenarioId: "scenario-1",
    name: "Base",
    branchLabel: null,
    parentId: null,
    updatedAt: "2026-01-10T08:05:00.000Z",
    archivedAt: null,
    lastFinalRunId: "run-a",
    seed: 42,
    ...overrides,
  };
}

function record(id: string, payload: Scenario, overrides: Partial<ScenarioRecord> = {}): ScenarioRecord {
  return {
    ...scenarioRecord,
    id,
    name: payload.name,
    scenario: payload,
    ...overrides,
  };
}

function run(overrides: Partial<RunRef> = {}): RunRef {
  return {
    id: "run-a",
    scenarioId: "scenario-1",
    seed: 42,
    engineVersion: "0.4.0",
    runs: 5_000,
    pinned: false,
    createdAt: "2026-01-10T08:05:00.000Z",
    summary: {},
    ...overrides,
  };
}

function comparison(): ProjectRunCompareResult {
  return {
    sameSeed: true,
    sameEngineVersion: true,
    runs: [
      {
        id: "run-a",
        scenarioId: "scenario-1",
        seed: 42,
        engineVersion: "0.4.0",
        result: simulationResult,
      },
      {
        id: "run-b",
        scenarioId: "scenario-2",
        seed: 42,
        engineVersion: "0.4.0",
        result: {
          ...simulationResult,
          metrics: { ...simulationResult.metrics, p50: 260_000 },
        },
      },
    ],
  };
}

const branches = [
  branch(),
  branch({ scenarioId: "scenario-2", name: "Variante", branchLabel: "Variante", parentId: "scenario-1" }),
];

async function findItem(name: string): Promise<HTMLElement> {
  return (await screen.findByText(name)).closest("li") as HTMLElement;
}

function renderScreen(overrides: { onOpenBranch?: (id: string) => Promise<void> } = {}) {
  return render(
    <BranchesScreen
      project={project}
      activeScenarioId="scenario-1"
      currency="XOF"
      onOpenBranch={overrides.onOpenBranch ?? (async () => undefined)}
    />,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  ipc.listBranches.mockResolvedValue({ branches });
  ipc.listVersions.mockResolvedValue({ versions: [] });
  ipc.listRuns.mockResolvedValue({
    runs: [run(), run({ id: "run-b", scenarioId: "scenario-2" })],
  });
  ipc.compareRuns.mockResolvedValue(comparison());
  ipc.getScenario.mockImplementation(async ({ scenarioId }: { scenarioId: string }) => ({
    scenario: scenarioId === "scenario-2" ? record("scenario-2", scenarioB) : record("scenario-1", scenarioA),
  }));
  ipc.archiveScenario.mockResolvedValue({
    scenario: record("scenario-1", scenarioA),
    archived: true,
    pinnedRuns: 0,
  });
  ipc.unarchiveScenario.mockResolvedValue({ scenario: record("scenario-1", scenarioA) });
  ipc.renameScenario.mockResolvedValue({ scenario: record("scenario-1", scenarioA) });
  ipc.createVersion.mockResolvedValue({
    version: {
      id: "version-1",
      projectId: project.id,
      scenarioId: "scenario-1",
      label: "Référence",
      seed: 42,
      engineVersion: "0.4.0",
      createdAt: "2026-01-10T08:05:00.000Z",
    },
  });
  ipc.branchProjectScenario.mockResolvedValue({
    scenario: record("new-branch", { ...scenarioA, name: "Variante C" }, { branchLabel: "Variante C" }),
  });
});

describe("BranchesScreen", () => {
  it("charge les branches, les runs et la comparaison", async () => {
    renderScreen();
    expect(await screen.findByText("Base")).toBeTruthy();
    expect(screen.getByText("Variante")).toBeTruthy();
    await waitFor(() => expect(ipc.listBranches).toHaveBeenCalled());
    expect(ipc.listRuns).toHaveBeenCalledWith({
      projectId: project.id,
      limit: 200,
    });
  });

  it("affiche le diff pur de deux branches sélectionnées", async () => {
    renderScreen();
    fireEvent.click(within(await findItem("Variante")).getByRole("button", { name: /Comparer la branche/ }));
    fireEvent.click(within(await findItem("Base")).getByRole("button", { name: /Comparer la branche/ }));

    expect(await screen.findByText(/Prix de vente unitaire · valeur/)).toBeTruthy();
    expect(screen.getByText("5 000")).toBeTruthy();
    expect(screen.getByText("5 500")).toBeTruthy();
  });

  it("archive une branche sans run épinglé", async () => {
    renderScreen();
    fireEvent.click(within(await findItem("Base")).getByRole("button", { name: "Archiver" }));
    await waitFor(() =>
      expect(ipc.archiveScenario).toHaveBeenCalledWith({
        projectId: project.id,
        scenarioId: "scenario-1",
        confirmPinned: false,
      }),
    );
  });

  it("demande confirmation si des runs épinglés référencent la branche", async () => {
    ipc.listRuns.mockResolvedValue({
      runs: [run({ pinned: true }), run({ id: "run-b", scenarioId: "scenario-2" })],
    });
    renderScreen();
    fireEvent.click(within(await findItem("Base")).getByRole("button", { name: "Archiver" }));

    expect(
      await screen.findByText("Des runs épinglés référencent cette branche"),
    ).toBeTruthy();
    expect(ipc.archiveScenario).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Confirmer l'archivage" }));
    await waitFor(() =>
      expect(ipc.archiveScenario).toHaveBeenCalledWith({
        projectId: project.id,
        scenarioId: "scenario-1",
        confirmPinned: true,
      }),
    );
  });

  it("annule un archivage via l'historique", async () => {
    renderScreen();
    fireEvent.click(within(await findItem("Base")).getByRole("button", { name: "Archiver" }));
    await waitFor(() => expect(ipc.archiveScenario).toHaveBeenCalled());

    const undo = screen.getByRole("button", { name: "Annuler" });
    await waitFor(() => expect(undo).toHaveProperty("disabled", false));
    fireEvent.click(undo);
    await waitFor(() =>
      expect(ipc.unarchiveScenario).toHaveBeenCalledWith({
        projectId: project.id,
        scenarioId: "scenario-1",
      }),
    );
  });

  it("duplique une branche et l'ouvre dans le cockpit", async () => {
    const onOpenBranch = vi.fn(async () => undefined);
    renderScreen({ onOpenBranch });

    fireEvent.click(within(await findItem("Base")).getByRole("button", { name: "Dupliquer" }));
    fireEvent.change(screen.getByLabelText(/Libellé de la branche issue de/), {
      target: { value: "Variante C" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Créer la branche" }));

    await waitFor(() =>
      expect(ipc.branchProjectScenario).toHaveBeenCalledWith({
        projectId: project.id,
        scenarioId: "scenario-1",
        label: "Variante C",
      }),
    );
    await waitFor(() => expect(onOpenBranch).toHaveBeenCalledWith("new-branch"));
  });

  it("enregistre une version depuis l'onglet Versions", async () => {
    renderScreen();
    fireEvent.click(await screen.findByRole("tab", { name: "Versions" }));
    fireEvent.change(screen.getByLabelText("Libellé de la nouvelle version"), {
      target: { value: "Référence" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    await waitFor(() =>
      expect(ipc.createVersion).toHaveBeenCalledWith({
        projectId: project.id,
        label: "Référence",
      }),
    );
  });

  it("annule la création d'une version via l'historique", async () => {
    renderScreen();
    fireEvent.click(await screen.findByRole("tab", { name: "Versions" }));
    fireEvent.change(screen.getByLabelText("Libellé de la nouvelle version"), {
      target: { value: "Référence" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
    await waitFor(() => expect(ipc.createVersion).toHaveBeenCalled());

    const undo = screen.getByRole("button", { name: "Annuler" });
    await waitFor(() => expect(undo).toHaveProperty("disabled", false));
    fireEvent.click(undo);
    await waitFor(() =>
      expect(ipc.deleteVersion).toHaveBeenCalledWith({
        projectId: project.id,
        versionId: "version-1",
      }),
    );
  });

  it("affiche une erreur lisible quand une action échoue", async () => {
    ipc.archiveScenario.mockRejectedValue(new Error("branche introuvable"));
    renderScreen();
    fireEvent.click(within(await findItem("Base")).getByRole("button", { name: "Archiver" }));

    expect(await screen.findByText("branche introuvable")).toBeTruthy();
  });
});
