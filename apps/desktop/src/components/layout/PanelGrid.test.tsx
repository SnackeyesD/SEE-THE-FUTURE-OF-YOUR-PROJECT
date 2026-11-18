import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  customLayout,
  layoutFromPreset,
  type LayoutState,
} from "../../store/layout";
import { PanelGrid } from "./PanelGrid";

function renderGrid(layout: LayoutState = layoutFromPreset("analyse")) {
  const onLayoutChange = vi.fn();
  const result = render(
    <PanelGrid
      layout={layout}
      onLayoutChange={onLayoutChange}
      left={<p>Hypothèses</p>}
      main={<p>Principal</p>}
      right={<p>Secondaire</p>}
      header={<p>KPI</p>}
      footer={<p>Frise</p>}
    />,
  );
  return { ...result, onLayoutChange };
}

describe("PanelGrid", () => {
  it("affiche les trois panneaux, la barre KPI et la frise", () => {
    renderGrid();

    expect(screen.getByRole("region", { name: "Hypothèses" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Principal" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Secondaire" })).toBeInTheDocument();
    expect(screen.getByText("KPI")).toBeInTheDocument();
    expect(screen.getByText("Frise")).toBeInTheDocument();
  });

  it("applique un preset", () => {
    const { onLayoutChange } = renderGrid();

    fireEvent.click(screen.getByRole("button", { name: "Disposition Pilotage" }));

    expect(onLayoutChange).toHaveBeenCalledWith(layoutFromPreset("pilotage"));
  });

  it("redimensionne au clavier en restant dans les bornes", () => {
    const layout = customLayout({ left: 0.2, main: 0.6, right: 0.2 });
    const { onLayoutChange } = renderGrid(layout);

    fireEvent.keyDown(
      screen.getByRole("separator", { name: "Redimensionner les hypothèses" }),
      { key: "ArrowLeft" },
    );

    expect(onLayoutChange).toHaveBeenCalledTimes(1);
    const next = onLayoutChange.mock.calls[0][0] as LayoutState;
    expect(next.preset).toBe("custom");
    expect(next.fractions.left).toBeCloseTo(0.18);
    expect(next.fractions.main).toBeCloseTo(0.62);
    expect(next.fractions.left + next.fractions.main + next.fractions.right).toBeCloseTo(1);
  });

  it("ne descend pas sous la fraction minimale", () => {
    const layout = customLayout({ left: 0.15, main: 0.65, right: 0.2 });
    const { onLayoutChange } = renderGrid(layout);

    fireEvent.keyDown(
      screen.getByRole("separator", { name: "Redimensionner les hypothèses" }),
      { key: "ArrowLeft" },
    );

    const next = onLayoutChange.mock.calls[0][0] as LayoutState;
    expect(next.fractions.left).toBeGreaterThanOrEqual(0.15);
    expect(next.fractions.main).toBeGreaterThanOrEqual(0.15);
  });

  it("affiche un panneau en plein écran et permet d'en sortir", () => {
    const layout = layoutFromPreset("analyse");
    const { onLayoutChange, rerender } = renderGrid(layout);

    rerender(
      <PanelGrid
        layout={{ ...layout, fullscreen: "main" }}
        onLayoutChange={onLayoutChange}
        left={<p>Hypothèses</p>}
        main={<p>Principal</p>}
        right={<p>Secondaire</p>}
      />,
    );

    expect(screen.getByRole("region", { name: "Principal" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Hypothèses" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Quitter le plein écran" }));
    expect(onLayoutChange).toHaveBeenCalledWith({ ...layout, fullscreen: null });
  });

  it("bascule le plein écran secondaire depuis la barre d'outils", () => {
    const { onLayoutChange } = renderGrid();

    fireEvent.click(screen.getByRole("button", { name: "Plein écran secondaire" }));

    expect(onLayoutChange).toHaveBeenCalledWith({
      ...layoutFromPreset("analyse"),
      fullscreen: "secondary",
    });
  });
});
