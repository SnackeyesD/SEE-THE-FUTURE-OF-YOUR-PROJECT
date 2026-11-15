import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { project, scenarioRecord } from "../test/fixtures";
import { SimulationScreen } from "./SimulationScreen";

function renderScreen(overrides: Partial<Parameters<typeof SimulationScreen>[0]> = {}) {
  const props = {
    project,
    scenario: scenarioRecord,
    run: null,
    progress: null,
    busy: false,
    error: "",
    onRun: vi.fn().mockResolvedValue(undefined),
    onOpenResults: vi.fn(),
    onBack: vi.fn(),
    ...overrides,
  };
  render(<SimulationScreen {...props} />);
  return props;
}

describe("SimulationScreen", () => {
  it("lance le moteur avec les paramètres saisis", async () => {
    const user = userEvent.setup();
    const props = renderScreen();

    expect(screen.getByRole("heading", { name: "Monte Carlo local" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Scénario de base" })).toBeInTheDocument();

    const runs = screen.getByLabelText(/Nombre de simulations/);
    await user.clear(runs);
    await user.type(runs, "5000");
    await user.click(screen.getByRole("button", { name: "Lancer la simulation" }));

    expect(props.onRun).toHaveBeenCalledWith({
      runs: 5000,
      seed: 42,
      histogramBins: 40,
    });
  });

  it("désactive le calcul quand les paramètres sont invalides", async () => {
    const user = userEvent.setup();
    renderScreen();

    const runs = screen.getByLabelText(/Nombre de simulations/);
    await user.clear(runs);
    await user.type(runs, "0");

    expect(screen.getByRole("button", { name: "Lancer la simulation" })).toBeDisabled();
  });

  it("affiche un état vide sans scénario et permet de revenir", async () => {
    const user = userEvent.setup();
    const props = renderScreen({ scenario: null });

    expect(screen.getByText("Hypothèses requises")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retour aux hypothèses" }));
    expect(props.onBack).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("button", { name: "Lancer la simulation" })).not.toBeInTheDocument();
  });

  it("montre la progression pendant un calcul", () => {
    renderScreen({ busy: true, progress: 0.4 });

    expect(screen.getByRole("progressbar", { name: "Calcul des scénarios" })).toHaveAttribute(
      "aria-valuenow",
      "40",
    );
  });
});
