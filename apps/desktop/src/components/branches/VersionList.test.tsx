import type { ScenarioVersionRef } from "@see/protocol";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { VersionList } from "./VersionList";

function version(overrides: Partial<ScenarioVersionRef> = {}): ScenarioVersionRef {
  return {
    id: "version-1",
    projectId: "project-1",
    scenarioId: "scenario-1",
    label: "Référence",
    seed: 7,
    engineVersion: "0.4.0",
    createdAt: "2026-01-10T08:05:00.000Z",
    ...overrides,
  };
}

describe("VersionList", () => {
  it("annonce l'absence de version", () => {
    render(
      <VersionList versions={[]} onCreate={vi.fn()} onRestore={vi.fn()} onDelete={vi.fn()} />,
    );
    expect(screen.getByText("Aucune version enregistrée")).toBeTruthy();
  });

  it("crée une version avec un libellé", () => {
    const onCreate = vi.fn();
    render(
      <VersionList versions={[]} onCreate={onCreate} onRestore={vi.fn()} onDelete={vi.fn()} />,
    );
    fireEvent.change(screen.getByLabelText("Libellé de la nouvelle version"), {
      target: { value: "Avant hausse" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
    expect(onCreate).toHaveBeenCalledWith("Avant hausse");
  });

  it("liste les métadonnées et restaure en branche", () => {
    const onRestore = vi.fn();
    render(
      <VersionList
        versions={[version()]}
        onCreate={vi.fn()}
        onRestore={onRestore}
        onDelete={vi.fn()}
      />,
    );
    expect(screen.getByText("Référence")).toBeTruthy();
    expect(screen.getByText(/graine 7/)).toBeTruthy();
    expect(screen.getByText(/moteur 0.4.0/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Restaurer en branche" }));
    expect(onRestore).toHaveBeenCalledWith(expect.objectContaining({ id: "version-1" }));
  });

  it("exige une confirmation explicite avant suppression", () => {
    const onDelete = vi.fn();
    render(
      <VersionList
        versions={[version()]}
        onCreate={vi.fn()}
        onRestore={vi.fn()}
        onDelete={onDelete}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Supprimer" }));
    expect(onDelete).not.toHaveBeenCalled();
    expect(screen.getByText("Supprimer cette version ?")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Confirmer la suppression" }));
    expect(onDelete).toHaveBeenCalledWith(expect.objectContaining({ id: "version-1" }));
  });

  it("désactive l'enregistrement sans libellé ou pendant une action", () => {
    render(
      <VersionList
        versions={[version()]}
        busy
        onCreate={vi.fn()}
        onRestore={vi.fn()}
        onDelete={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: "Enregistrer" })).toHaveProperty(
      "disabled",
      true,
    );
    expect(screen.getByRole("button", { name: "Restaurer en branche" })).toHaveProperty(
      "disabled",
      true,
    );
  });
});
