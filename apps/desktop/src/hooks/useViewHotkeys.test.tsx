import { fireEvent, render, renderHook, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useViewHotkeys } from "./useViewHotkeys";

const VIEWS = ["projects", "interview", "brief", "hypotheses", "simulation", "results"];

function setup(options: { enabled?: boolean } = {}) {
  const onSelect = vi.fn();
  render(
    <div>
      <input aria-label="champ" />
      <div data-hotkeys-scope="true">
        <input aria-label="champ du dialogue" />
      </div>
    </div>,
  );
  renderHook(() => useViewHotkeys({ views: VIEWS, onSelect, enabled: options.enabled }));
  return { onSelect, input: screen.getByLabelText("champ") };
}

describe("useViewHotkeys", () => {
  it("sélectionne la vue correspondant au chiffre", () => {
    const { onSelect } = setup();

    fireEvent.keyDown(document.body, { key: "1" });
    expect(onSelect).toHaveBeenLastCalledWith("projects");

    fireEvent.keyDown(document.body, { key: "6" });
    expect(onSelect).toHaveBeenLastCalledWith("results");
  });

  it("ignore un chiffre hors bornes", () => {
    const { onSelect } = setup();

    fireEvent.keyDown(document.body, { key: "7" });
    fireEvent.keyDown(document.body, { key: "9" });
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("ne capture rien dans un champ, un dialogue ou avec un modificateur", () => {
    const { onSelect, input } = setup();

    fireEvent.keyDown(input, { key: "2" });
    fireEvent.keyDown(screen.getByLabelText("champ du dialogue"), { key: "3" });
    fireEvent.keyDown(document.body, { key: "4", ctrlKey: true });
    fireEvent.keyDown(document.body, { key: "5", altKey: true });

    expect(onSelect).not.toHaveBeenCalled();
  });

  it("ne fait rien quand les raccourcis sont désactivés", () => {
    const { onSelect } = setup({ enabled: false });

    fireEvent.keyDown(document.body, { key: "1" });
    expect(onSelect).not.toHaveBeenCalled();
  });
});
