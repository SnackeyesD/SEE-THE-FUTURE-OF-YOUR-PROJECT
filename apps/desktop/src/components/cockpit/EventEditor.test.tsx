import type { ScenarioEvent } from "@see/protocol";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EventEditor } from "./EventEditor";

function makeEvent(overrides: Partial<ScenarioEvent> = {}): ScenarioEvent {
  return {
    id: "event-1",
    type: "supplier_price_rise",
    startMonth: 2,
    durationMonths: 3,
    target: "unit_cost",
    mode: "multiplicative",
    probability: 1,
    magnitude: { kind: "triangular", low: 1.05, mode: 1.15, high: 1.3 },
    enabled: true,
    ...overrides,
  };
}

function renderEditor(
  options: {
    event?: ScenarioEvent;
    horizon?: number;
    error?: string;
    onApply?: (patch: Partial<ScenarioEvent>) => Promise<boolean> | void;
  } = {},
) {
  const onApply = vi.fn(options.onApply ?? (() => undefined));
  const onClose = vi.fn();
  render(
    <EventEditor
      event={options.event ?? makeEvent()}
      horizon={options.horizon ?? 12}
      error={options.error}
      onApply={onApply}
      onClose={onClose}
    />,
  );
  return { onApply, onClose };
}

describe("EventEditor", () => {
  it("applique une fenêtre valide et convertit la probabilité", async () => {
    const { onApply } = renderEditor();

    fireEvent.change(screen.getByLabelText(/Mois de début/), { target: { value: "4" } });
    fireEvent.change(screen.getByLabelText(/Durée \(mois\)/), { target: { value: "5" } });
    fireEvent.change(screen.getByLabelText(/Probabilité d'occurrence/), {
      target: { value: "40" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Appliquer et relancer" }));

    await waitFor(() => expect(onApply).toHaveBeenCalledTimes(1));
    expect(onApply.mock.calls[0][0]).toMatchObject({
      startMonth: 4,
      durationMonths: 5,
      probability: 0.4,
      target: "unit_cost",
      mode: "multiplicative",
    });
  });

  it("refuse une fenêtre qui dépasse l'horizon sans appeler le parent", () => {
    const { onApply } = renderEditor({ horizon: 6 });

    fireEvent.change(screen.getByLabelText(/Mois de début/), { target: { value: "5" } });
    fireEvent.change(screen.getByLabelText(/Durée \(mois\)/), { target: { value: "4" } });
    fireEvent.click(screen.getByRole("button", { name: "Appliquer et relancer" }));

    expect(screen.getByText(/au-delà de l'horizon \(6\)/)).toBeInTheDocument();
    expect(onApply).not.toHaveBeenCalled();
  });

  it("refuse une intensité multiplicative qui peut devenir négative", () => {
    const { onApply } = renderEditor({
      event: makeEvent({
        magnitude: { kind: "normal", mean: 1.2, std: 0.2 },
      }),
    });

    fireEvent.click(screen.getByRole("button", { name: "Appliquer et relancer" }));

    expect(screen.getByText(/peut devenir négative/)).toBeInTheDocument();
    expect(onApply).not.toHaveBeenCalled();
  });

  it("affiche l'erreur du moteur sans fermer le dialogue", () => {
    renderEditor({ error: "Cible inconnue pour ce type d'événement." });

    expect(screen.getByText("Refusé par le moteur")).toBeInTheDocument();
    expect(
      screen.getByText("Cible inconnue pour ce type d'événement."),
    ).toBeInTheDocument();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("reste ouvert et désactive le bouton pendant l'attente du sidecar", async () => {
    let resolve: (accepted: boolean) => void = () => undefined;
    const onApply = vi.fn(
      () =>
        new Promise<boolean>((done) => {
          resolve = done;
        }),
    );
    renderEditor({ onApply });

    fireEvent.click(screen.getByRole("button", { name: "Appliquer et relancer" }));

    expect(await screen.findByRole("button", { name: "Calcul en cours…" })).toBeDisabled();

    resolve(false);
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Appliquer et relancer" }),
      ).toBeEnabled(),
    );
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
});
