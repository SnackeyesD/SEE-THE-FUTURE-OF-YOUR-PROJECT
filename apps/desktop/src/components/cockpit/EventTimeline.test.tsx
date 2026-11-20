import type { ScenarioEvent } from "@see/protocol";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EventTimeline } from "./EventTimeline";

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

function setup(events: ScenarioEvent[] = [makeEvent()]) {
  const actions = {
    onSelect: vi.fn(),
    onChange: vi.fn(),
    onToggle: vi.fn(),
    onDuplicate: vi.fn(),
    onDelete: vi.fn(),
    onEdit: vi.fn(),
    onOpenCatalog: vi.fn(),
    onSelectMonth: vi.fn(),
  };
  const view = render(
    <EventTimeline
      events={events}
      horizon={12}
      selectedId={null}
      {...actions}
    />,
  );
  return { actions, ...view };
}

function block() {
  return screen.getByRole("button", { name: /Hausse du prix fournisseur — mois/ });
}

/**
 * jsdom n'implémente pas `PointerEvent` : `fireEvent.pointerDown` retombe sur
 * `Event`, qui ignore `clientX`. On dispatche donc un `MouseEvent` portant le
 * type pointeur, ce que React traite comme un événement pointeur complet.
 */
function firePointer(
  node: Element,
  type: "pointerdown" | "pointermove" | "pointerup" | "pointercancel",
  clientX: number,
): void {
  const event = new MouseEvent(type, {
    bubbles: true,
    cancelable: true,
    clientX,
    clientY: 0,
  });
  Object.defineProperty(event, "pointerId", { configurable: true, value: 1 });
  fireEvent(node, event);
}

describe("EventTimeline", () => {
  it("déplace, redimensionne et active un événement au clavier", () => {
    const { actions } = setup();

    fireEvent.keyDown(block(), { key: "ArrowRight" });
    expect(actions.onChange).toHaveBeenLastCalledWith(
      "event-1",
      { startMonth: 3, durationMonths: 3 },
      true,
    );

    fireEvent.keyDown(block(), { key: "ArrowRight", shiftKey: true });
    expect(actions.onChange).toHaveBeenLastCalledWith(
      "event-1",
      { startMonth: 2, durationMonths: 4 },
      true,
    );

    fireEvent.keyDown(block(), { key: "ArrowLeft", altKey: true });
    expect(actions.onChange).toHaveBeenLastCalledWith(
      "event-1",
      { startMonth: 1, durationMonths: 4 },
      true,
    );

    fireEvent.keyDown(block(), { key: " " });
    expect(actions.onToggle).toHaveBeenCalledWith("event-1");

    fireEvent.keyDown(block(), { key: "Enter" });
    expect(actions.onEdit).toHaveBeenCalledWith("event-1");

    fireEvent.keyDown(block(), { key: "Delete" });
    expect(actions.onDelete).toHaveBeenCalledWith("event-1");
  });

  it("valide un glissement au relâchement", () => {
    const { actions, container } = setup();
    const track = container.querySelector<HTMLElement>(".cockpit-timeline__track");
    if (!track) throw new Error("piste absente");
    Object.defineProperty(track, "clientWidth", { configurable: true, value: 120 });

    firePointer(block(), "pointerdown", 0);
    firePointer(block(), "pointermove", 30);
    firePointer(block(), "pointerup", 30);

    expect(actions.onChange).toHaveBeenCalledWith(
      "event-1",
      { startMonth: 5, durationMonths: 3 },
      true,
    );
  });

  it("n'enregistre rien sur pointercancel", () => {
    const { actions, container } = setup();
    const track = container.querySelector<HTMLElement>(".cockpit-timeline__track");
    if (!track) throw new Error("piste absente");
    Object.defineProperty(track, "clientWidth", { configurable: true, value: 120 });

    firePointer(block(), "pointerdown", 0);
    firePointer(block(), "pointermove", 30);
    firePointer(block(), "pointercancel", 30);

    expect(actions.onChange).not.toHaveBeenCalled();
  });

  it("propose les actions du menu contextuel", () => {
    const { actions } = setup();

    fireEvent.click(
      screen.getByRole("button", { name: "Actions pour Hausse du prix fournisseur" }),
    );
    const menu = screen.getByRole("menu", { name: "Actions de l'événement" });

    fireEvent.click(within(menu).getByRole("menuitem", { name: "Dupliquer" }));
    expect(actions.onDuplicate).toHaveBeenCalledWith("event-1");

    fireEvent.click(
      screen.getByRole("button", { name: "Actions pour Hausse du prix fournisseur" }),
    );
    fireEvent.click(
      within(screen.getByRole("menu", { name: "Actions de l'événement" })).getByRole(
        "menuitem",
        { name: "Supprimer" },
      ),
    );
    expect(actions.onDelete).toHaveBeenCalledWith("event-1");
  });

  it("sélectionne le mois en cliquant sur la piste", () => {
    const { actions, container } = setup([]);
    const track = container.querySelector<HTMLElement>(".cockpit-timeline__track");
    if (!track) throw new Error("piste absente");
    track.getBoundingClientRect = () =>
      ({
        left: 0,
        top: 0,
        right: 120,
        bottom: 40,
        width: 120,
        height: 40,
        x: 0,
        y: 0,
        toJSON: () => ({}),
      }) as DOMRect;

    firePointer(track, "pointerdown", 60);

    expect(actions.onSelectMonth).toHaveBeenCalledWith(7);
    expect(actions.onSelect).toHaveBeenCalledWith(null);
  });
});
