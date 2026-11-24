import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { runRecord } from "../test/fixtures";
import { ResultsScreen } from "./ResultsScreen";

function renderScreen(overrides: Partial<Parameters<typeof ResultsScreen>[0]> = {}) {
  const props = {
    run: runRecord,
    narration: "",
    narrationBusy: false,
    reportBusy: false,
    error: "",
    onNarrate: vi.fn().mockResolvedValue(undefined),
    onExportReport: vi.fn().mockResolvedValue(undefined),
    onBack: vi.fn(),
    ...overrides,
  };
  render(<ResultsScreen {...props} />);
  return props;
}

describe("ResultsScreen", () => {
  it("affiche les agrégats calculés par le moteur", () => {
    renderScreen();

    expect(
      screen.getByRole("heading", { name: "Scénario de base", level: 1 }),
    ).toBeInTheDocument();
    expect(screen.getByText("Distribution du profit")).toBeInTheDocument();
    expect(screen.getByText("Probabilité de perte")).toBeInTheDocument();
    expect(screen.getByText("Seuil de rentabilité")).toBeInTheDocument();
    expect(screen.getByText("Contribution des hypothèses")).toBeInTheDocument();
  });

  it("valide une narration cohérente avec le résultat", () => {
    renderScreen({ narration: "Le profit moyen atteint 250 000 FCFA." });

    expect(screen.getByText("Cohérence vérifiée")).toBeInTheDocument();
    expect(screen.queryByText("Chiffres non reconnus")).not.toBeInTheDocument();
  });

  it("alerte sur un chiffre absent du résultat", () => {
    renderScreen({ narration: "Le profit moyen sera de 123 456 789 FCFA." });

    expect(screen.getByText("Chiffres non reconnus")).toBeInTheDocument();
    expect(screen.getAllByText(/123 456 789/).length).toBeGreaterThan(0);
  });

  it("demande la narration à l'agent", async () => {
    const user = userEvent.setup();
    const props = renderScreen();

    await user.click(screen.getByRole("button", { name: "Générer la narration" }));
    expect(props.onNarrate).toHaveBeenCalledTimes(1);
  });

  it("demande l'export du dossier", async () => {
    const user = userEvent.setup();
    const props = renderScreen();

    await user.click(screen.getByRole("button", { name: "Exporter le dossier" }));
    expect(props.onExportReport).toHaveBeenCalledTimes(1);
  });

  it("affiche un état vide sans run", () => {
    renderScreen({ run: null });

    expect(screen.getByText("Aucun résultat à afficher")).toBeInTheDocument();
  });
});
