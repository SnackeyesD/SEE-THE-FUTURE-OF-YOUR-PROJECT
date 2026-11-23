import type { BranchRef } from "@see/protocol";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { BranchList } from "./BranchList";

function branch(overrides: Partial<BranchRef> = {}): BranchRef {
  return {
    scenarioId: "scenario-1",
    name: "Base",
    branchLabel: "Variante A",
    parentId: null,
    updatedAt: "2026-01-10T08:05:00.000Z",
    archivedAt: null,
    lastFinalRunId: "run-1",
    seed: 42,
    ...overrides,
  };
}

function setup(branches: BranchRef[], overrides: Record<string, unknown> = {}) {
  const actions = {
    onSelectCompare: vi.fn(),
    onOpen: vi.fn(),
    onDuplicate: vi.fn(),
    onRename: vi.fn(),
    onArchive: vi.fn(),
    onUnarchive: vi.fn(),
  };
  const view = render(
    <BranchList
      branches={branches}
      activeBranchId="scenario-1"
      compareIds={[]}
      limitReached={false}
      {...actions}
      {...overrides}
    />,
  );
  return { actions, ...view };
}

describe("BranchList", () => {
  it("affiche le libellé, le parent et la graine du dernier run", () => {
    setup([
      branch({ scenarioId: "scenario-1", parentId: null, branchLabel: null, name: "Racine" }),
      branch({ scenarioId: "child", parentId: "scenario-1", branchLabel: "Variante B" }),
    ]);

    expect(screen.getByText("Racine")).toBeTruthy();
    expect(screen.getByText("Variante B")).toBeTruthy();
    expect(screen.getByText("scénario racine")).toBeTruthy();
    expect(screen.getByText(/branche de Racine/)).toBeTruthy();
    expect(screen.getAllByText(/Graine du dernier run final/)).toHaveLength(2);
    expect(screen.getByText("branche courante")).toBeTruthy();
  });

  it("sélectionne une branche pour la comparaison", () => {
    const { actions } = setup([branch()]);
    fireEvent.click(screen.getByRole("button", { name: /Comparer la branche/ }));
    expect(actions.onSelectCompare).toHaveBeenCalledWith("scenario-1");
  });

  it("duplique avec un libellé saisi", () => {
    const { actions } = setup([branch()]);
    fireEvent.click(screen.getByRole("button", { name: "Dupliquer" }));
    const field = screen.getByLabelText(/Libellé de la branche issue de/);
    fireEvent.change(field, { target: { value: "Variante C" } });
    fireEvent.click(screen.getByRole("button", { name: "Créer la branche" }));

    expect(actions.onDuplicate).toHaveBeenCalledWith(
      expect.objectContaining({ scenarioId: "scenario-1" }),
      "Variante C",
    );
  });

  it("renomme via le formulaire local", () => {
    const { actions } = setup([branch()]);
    fireEvent.click(screen.getByRole("button", { name: "Renommer" }));
    const field = screen.getByLabelText(/Nouveau nom pour/);
    fireEvent.change(field, { target: { value: "Nouvelle base" } });
    fireEvent.click(screen.getByRole("button", { name: "Valider" }));

    expect(actions.onRename).toHaveBeenCalledWith(
      expect.objectContaining({ scenarioId: "scenario-1" }),
      "Nouvelle base",
    );
  });

  it("propose l'archivage, et la restauration pour une branche archivée", () => {
    const active = setup([branch()]);
    fireEvent.click(screen.getByRole("button", { name: "Archiver" }));
    expect(active.actions.onArchive).toHaveBeenCalled();
    active.unmount();

    const archived = branch({ scenarioId: "old", archivedAt: "2026-02-01T00:00:00.000Z" });
    const view = setup([archived]);
    expect(screen.getByText("archivée")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Archiver" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Restaurer" }));
    expect(view.actions.onUnarchive).toHaveBeenCalled();
  });

  it("désactive la duplication quand la limite est atteinte", () => {
    setup([branch()], { limitReached: true });
    expect(screen.getByRole("button", { name: "Dupliquer" })).toHaveProperty(
      "disabled",
      true,
    );
  });

  it("affiche l'état vide sans plantage", () => {
    const view = render(
      <BranchList
        branches={[]}
        activeBranchId={null}
        compareIds={[]}
        limitReached={false}
      />,
    );
    expect(view.container.querySelectorAll(".branch-list__item")).toHaveLength(0);
    expect(screen.queryByRole("listitem")).toBeNull();
  });
});

describe("BranchList accessibility", () => {
  it("marque l'état de comparaison avec aria-pressed", () => {
    render(
      <BranchList
        branches={[branch()]}
        activeBranchId={null}
        compareIds={["scenario-1"]}
        limitReached={false}
      />,
    );
    const button = screen.getByRole("button", { name: /Comparer la branche/ });
    expect(button.getAttribute("aria-pressed")).toBe("true");
    expect(within(button).getByText("Comparée")).toBeTruthy();
  });
});
