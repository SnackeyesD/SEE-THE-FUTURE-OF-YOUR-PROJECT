import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TriHandleSlider } from "./TriHandleSlider";

function setup(overrides: Partial<Parameters<typeof TriHandleSlider>[0]> = {}) {
  const onChange = vi.fn();
  const view = render(
    <TriHandleSlider
      label="Prix de vente"
      unit="FCFA"
      value={{ low: 10, mode: 50, high: 90 }}
      domain={[0, 100]}
      onChange={onChange}
      {...overrides}
    />,
  );
  return { ...view, onChange };
}

describe("TriHandleSlider", () => {
  it("expose trois curseurs accessibles avec unité et bornes", () => {
    setup();

    const min = screen.getByRole("slider", { name: "Prix de vente — minimum" });
    const mode = screen.getByRole("slider", { name: "Prix de vente — mode" });
    const max = screen.getByRole("slider", { name: "Prix de vente — maximum" });

    expect(min).toHaveAttribute("aria-valuemin", "0");
    expect(min).toHaveAttribute("aria-valuemax", "50");
    expect(mode).toHaveAttribute("aria-valuemin", "10");
    expect(mode).toHaveAttribute("aria-valuemax", "90");
    expect(max).toHaveAttribute("aria-valuemax", "100");
    expect(mode).toHaveAttribute("aria-valuetext", "50 FCFA");
    expect(mode).toHaveAttribute("aria-valuenow", "50");
  });

  it("avance d'un pas au clavier et commite immédiatement", () => {
    const { onChange } = setup();
    fireEvent.keyDown(screen.getByRole("slider", { name: "Prix de vente — mode" }), {
      key: "ArrowRight",
    });
    expect(onChange).toHaveBeenCalledWith({ low: 10, mode: 51, high: 90 }, true);
  });

  it("ne laisse pas le mode dépasser le maximum", () => {
    const { onChange } = setup({
      value: { low: 10, mode: 90, high: 90 },
    });
    fireEvent.keyDown(screen.getByRole("slider", { name: "Prix de vente — mode" }), {
      key: "ArrowRight",
    });
    expect(onChange).toHaveBeenCalledWith({ low: 10, mode: 90, high: 90 }, true);
  });

  it("ne laisse pas le minimum dépasser le mode", () => {
    const { onChange } = setup({ value: { low: 10, mode: 10, high: 90 } });
    fireEvent.keyDown(screen.getByRole("slider", { name: "Prix de vente — minimum" }), {
      key: "ArrowRight",
    });
    expect(onChange).toHaveBeenCalledWith({ low: 10, mode: 10, high: 90 }, true);
  });

  it("gère Page↑/↓ et Home/End", () => {
    const { onChange } = setup();
    const mode = screen.getByRole("slider", { name: "Prix de vente — mode" });
    fireEvent.keyDown(mode, { key: "PageUp" });
    expect(onChange).toHaveBeenLastCalledWith({ low: 10, mode: 60, high: 90 }, true);

    fireEvent.keyDown(mode, { key: "Home" });
    expect(onChange).toHaveBeenLastCalledWith({ low: 10, mode: 10, high: 90 }, true);

    fireEvent.keyDown(mode, { key: "End" });
    expect(onChange).toHaveBeenLastCalledWith({ low: 10, mode: 90, high: 90 }, true);
  });

  it("ouvre une saisie numérique au double-clic et la valide", () => {
    const { onChange } = setup();
    fireEvent.doubleClick(screen.getByRole("slider", { name: "Prix de vente — mode" }));

    const editor = screen.getByRole("textbox", { name: "Prix de vente — mode (saisie)" });
    fireEvent.change(editor, { target: { value: "72" } });
    fireEvent.keyDown(editor, { key: "Enter" });

    expect(onChange).toHaveBeenCalledWith({ low: 10, mode: 72, high: 90 }, true);
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("annule la saisie avec Échap", () => {
    const { onChange } = setup();
    fireEvent.doubleClick(screen.getByRole("slider", { name: "Prix de vente — maximum" }));
    const editor = screen.getByRole("textbox");
    fireEvent.change(editor, { target: { value: "5" } });
    fireEvent.keyDown(editor, { key: "Escape" });

    expect(onChange).not.toHaveBeenCalled();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("désactive les poignées quand le paramètre est verrouillé", () => {
    const { onChange } = setup({ disabled: true });
    const mode = screen.getByRole("slider", { name: "Prix de vente — mode" });
    expect(mode).toHaveAttribute("tabindex", "-1");
    expect(mode).toHaveAttribute("aria-disabled", "true");

    fireEvent.keyDown(mode, { key: "ArrowRight" });
    fireEvent.doubleClick(mode);
    expect(onChange).not.toHaveBeenCalled();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });
});
