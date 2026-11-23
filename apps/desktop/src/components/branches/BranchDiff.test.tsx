import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { DiffEntry } from "../../lib/scenarioDiff";
import { BranchDiff } from "./BranchDiff";

const entries: DiffEntry[] = [
  {
    path: "horizonMonths",
    label: "Horizon (mois)",
    kind: "changed",
    before: 12,
    after: 18,
  },
  {
    path: "assumptions.unit_price.value",
    label: "Prix de vente · valeur",
    kind: "changed",
    before: 5_000,
    after: 5_500,
  },
  {
    path: "assumptions.unit_cost",
    label: "Coût unitaire",
    kind: "removed",
    before: { value: 3_000 },
  },
  {
    path: "events[ev2]",
    label: "Entrée d'un concurrent",
    kind: "event-added",
    after: { id: "ev2" },
  },
];

describe("BranchDiff", () => {
  it("annonce l'absence de différence", () => {
    render(<BranchDiff entries={[]} />);
    expect(screen.getByRole("status").textContent).toContain("Aucune différence");
  });

  it("groupe en-tête, hypothèses et événements avec les valeurs formatées", () => {
    render(
      <BranchDiff entries={entries} leftLabel="Racine" rightLabel="Variante" />,
    );

    expect(screen.getByRole("heading", { name: "En-tête du scénario" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Hypothèses" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Événements" })).toBeTruthy();

    expect(screen.getByText("12")).toBeTruthy();
    expect(screen.getByText("18")).toBeTruthy();
    expect(screen.getByText("5 000")).toBeTruthy();
    expect(screen.getByText("5 500")).toBeTruthy();
    expect(screen.getAllByText("modifié").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("supprimé")).toBeTruthy();
    expect(screen.getByText("événement ajouté")).toBeTruthy();
    expect(screen.getByText("assumptions.unit_price.value")).toBeTruthy();
  });

  it("nomme les deux branches dans les en-têtes de colonnes", () => {
    render(<BranchDiff entries={entries} leftLabel="Racine" rightLabel="Variante" />);
    const table = screen.getAllByRole("table")[0];
    expect(table.textContent).toContain("Racine");
    expect(table.textContent).toContain("Variante");
  });
});
