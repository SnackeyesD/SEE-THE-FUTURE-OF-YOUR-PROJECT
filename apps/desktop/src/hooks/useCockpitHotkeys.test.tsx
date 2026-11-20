import { fireEvent, render, renderHook, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useCockpitHotkeys } from "./useCockpitHotkeys";

function setup() {
  const actions = {
    onTogglePlayback: vi.fn(),
    onMonthStep: vi.fn(),
    onMonthEdge: vi.fn(),
    onToggleFullscreen: vi.fn(),
    onOpenPalette: vi.fn(),
    onOpenHelp: vi.fn(),
    onSave: vi.fn(),
    onEscape: vi.fn(),
  };
  const { container } = render(
    <div>
      <input aria-label="champ" />
      <button type="button">Action</button>
      <div data-hotkeys-timeline="true">
        <span>bloc</span>
      </div>
      <div data-hotkeys-scope="true">
        <input aria-label="champ du dialogue" />
      </div>
    </div>,
  );
  renderHook(() => useCockpitHotkeys(actions));
  return {
    actions,
    input: screen.getByLabelText("champ"),
    button: screen.getByRole("button", { name: "Action" }),
    timeline: container.querySelector<HTMLElement>("[data-hotkeys-timeline]")!,
    modalInput: screen.getByLabelText("champ du dialogue"),
  };
}

describe("useCockpitHotkeys", () => {
  it("déplace le temps et bascule la lecture hors des zones interactives", () => {
    const { actions } = setup();

    fireEvent.keyDown(document.body, { key: " " });
    expect(actions.onTogglePlayback).toHaveBeenCalledTimes(1);

    fireEvent.keyDown(document.body, { key: "ArrowRight" });
    expect(actions.onMonthStep).toHaveBeenCalledWith(1);

    fireEvent.keyDown(document.body, { key: "Home" });
    expect(actions.onMonthEdge).toHaveBeenCalledWith("first");
  });

  it("laisse Espace activer un bouton au lieu de lancer la lecture", () => {
    const { actions, button } = setup();
    fireEvent.keyDown(button, { key: " " });
    expect(actions.onTogglePlayback).not.toHaveBeenCalled();
  });

  it("ne capture pas les flèches dans un champ", () => {
    const { actions, input } = setup();
    fireEvent.keyDown(input, { key: "ArrowLeft" });
    fireEvent.keyDown(input, { key: " " });
    expect(actions.onMonthStep).not.toHaveBeenCalled();
    expect(actions.onTogglePlayback).not.toHaveBeenCalled();
  });

  it("laisse la frise gérer ses propres flèches", () => {
    const { actions, timeline } = setup();
    fireEvent.keyDown(timeline, { key: "ArrowRight" });
    expect(actions.onMonthStep).not.toHaveBeenCalled();
  });

  it("n'ouvre pas la palette pendant la saisie", () => {
    const { actions, input } = setup();
    fireEvent.keyDown(input, { key: "k", ctrlKey: true });
    expect(actions.onOpenPalette).not.toHaveBeenCalled();

    fireEvent.keyDown(document.body, { key: "k", ctrlKey: true });
    expect(actions.onOpenPalette).toHaveBeenCalledTimes(1);
  });

  it("suspend tous les raccourcis de fond derrière un dialogue", () => {
    const { actions, modalInput } = setup();

    fireEvent.keyDown(modalInput, { key: "k", ctrlKey: true });
    fireEvent.keyDown(modalInput, { key: "ArrowRight" });
    fireEvent.keyDown(modalInput, { key: "Escape" });

    expect(actions.onOpenPalette).not.toHaveBeenCalled();
    expect(actions.onMonthStep).not.toHaveBeenCalled();
    expect(actions.onEscape).not.toHaveBeenCalled();
  });

  it("gère plein écran, aide et sauvegarde", () => {
    const { actions } = setup();

    fireEvent.keyDown(document.body, { key: "f" });
    fireEvent.keyDown(document.body, { key: "?" });
    fireEvent.keyDown(document.body, { key: "s", ctrlKey: true });

    expect(actions.onToggleFullscreen).toHaveBeenCalledTimes(1);
    expect(actions.onOpenHelp).toHaveBeenCalledTimes(1);
    expect(actions.onSave).toHaveBeenCalledTimes(1);
  });
});
