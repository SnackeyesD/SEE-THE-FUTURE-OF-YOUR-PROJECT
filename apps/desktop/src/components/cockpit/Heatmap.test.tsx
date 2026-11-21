import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Heatmap, heatColor } from "./Heatmap";

function renderHeatmap(onApply = vi.fn()) {
  render(
    <Heatmap
      xValues={[10, 20]}
      yValues={[100, 200]}
      rows={[[1, 2], [3, null]]}
      metric="profit_p50"
      xLabel="Prix"
      yLabel="Coût"
      currency="XOF"
      current={[20, 100]}
      onApply={onApply}
    />,
  );
  return onApply;
}

describe("heatColor", () => {
  it("oriente les paliers selon le sens favorable de la métrique", () => {
    expect(heatColor(10, 0, 10)).toBe("var(--heat-4)");
    expect(heatColor(0, 0, 10)).toBe("var(--heat-0)");
    expect(heatColor(10, 0, 10, true)).toBe("var(--heat-0)");
    expect(heatColor(Number.NaN, 0, 10)).toBe("var(--heat-empty)");
  });
});

describe("Heatmap", () => {
  it("applique les coordonnées d'une cellule et marque le point courant", () => {
    const onApply = renderHeatmap();
    const cells = screen.getAllByRole("gridcell");

    expect(cells).toHaveLength(4);
    expect(cells[1]).toHaveAttribute("aria-current", "true");
    expect(cells[3]).toBeDisabled();
    fireEvent.click(cells[0]);
    expect(onApply).toHaveBeenCalledWith(10, 100);
  });

  it("expose les valeurs dans un tableau alternatif", () => {
    renderHeatmap();

    fireEvent.click(screen.getByText("Tableau des valeurs"));
    const table = screen.getByRole("table", { name: "Valeurs de la surface" });
    expect(table).toHaveTextContent("100");
    expect(table).toHaveTextContent("200");
    expect(table).toHaveTextContent("en attente");
  });
});
