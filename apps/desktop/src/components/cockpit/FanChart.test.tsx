import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { FanChart } from "@see/ui";

const points = [
  { month: 1, p10: 0, p50: 100, p90: 200 },
  { month: 2, p10: 50, p50: 150, p90: 250 },
  { month: 3, p10: 100, p50: 200, p90: 300 },
];

const cdf = [
  { value: 0, probability: 0.1 },
  { value: 200, probability: 0.9 },
];

describe("FanChart", () => {
  it("affiche une surface, une médiane et un tableau alternatif", () => {
    const { container } = render(<FanChart points={points} title="Trésorerie" />);

    expect(container.querySelector(".viz__fan-band")).not.toBeNull();
    expect(container.querySelector(".viz__fan-median")).not.toBeNull();
    expect(screen.getByText("Données du graphique")).toBeInTheDocument();
    expect(screen.getAllByRole("row")).toHaveLength(4);
    expect(screen.getByRole("row", { name: /M2/ })).toBeInTheDocument();
  });

  it("affiche un état vide sans bande disponible", () => {
    render(<FanChart points={[]} title="Trésorerie" />);
    expect(
      screen.getByText("Aucune bande P10–P90 disponible pour ce calcul."),
    ).toBeInTheDocument();
  });

  it("dessine le seuil et sa probabilité issue de la CDF", () => {
    render(
      <FanChart
        points={points}
        threshold={{ value: 100, label: "Trésorerie minimale", cdf }}
      />,
    );

    expect(screen.getByText(/Trésorerie minimale · 100 · 50,0 %/)).toBeInTheDocument();
    expect(
      screen.getByText(/P\(trésorerie minimale < 100\) = 50,0 %/),
    ).toBeInTheDocument();
  });

  it("signale une probabilité indisponible sans CDF", () => {
    render(<FanChart points={points} threshold={{ value: 100, label: "Seuil" }} />);
    expect(screen.getByText(/Seuil · 100 · non disponible/)).toBeInTheDocument();
    expect(screen.queryByText(/P\(trésorerie minimale/)).not.toBeInTheDocument();
  });

  it("déplace le seuil au clavier dans les bornes du domaine", () => {
    const onChange = vi.fn();
    const onCommit = vi.fn();
    render(
      <FanChart
        points={points}
        threshold={{
          value: 100,
          label: "Trésorerie minimale",
          cdf,
          onChange,
          onCommit,
        }}
      />,
    );

    const slider = screen.getByRole("slider", { name: "Trésorerie minimale" });
    expect(slider).toHaveAttribute("aria-valuemin", "0");
    expect(slider).toHaveAttribute("aria-valuemax", "300");

    fireEvent.keyDown(slider, { key: "ArrowUp" });
    expect(onChange).toHaveBeenLastCalledWith(103);
    expect(onCommit).toHaveBeenLastCalledWith(103);

    fireEvent.keyDown(slider, { key: "End" });
    expect(onChange).toHaveBeenLastCalledWith(300);

    fireEvent.keyDown(slider, { key: "PageDown" });
    expect(onChange.mock.calls.at(-1)?.[0]).toBeLessThan(300);
  });

  it("sélectionne un mois au clavier et affiche la valeur", () => {
    const onSelectMonth = vi.fn();
    render(
      <FanChart points={points} selectedMonth={1} onSelectMonth={onSelectMonth} />,
    );

    expect(screen.getByText("M1 — P10 0 · P50 100 · P90 200")).toBeInTheDocument();

    const group = screen.getByRole("group", { name: /navigation clavier/ });
    fireEvent.keyDown(group, { key: "ArrowRight" });
    expect(onSelectMonth).toHaveBeenCalledWith(2);

    fireEvent.keyDown(group, { key: "End" });
    expect(onSelectMonth).toHaveBeenCalledWith(3);
  });

  it("limite les fantômes à trois et affiche leur graine", () => {
    const ghosts = Array.from({ length: 4 }, (_, index) => ({
      id: `g${index}`,
      label: `Run ${index}`,
      seed: 10 + index,
      points,
    }));
    const { container } = render(<FanChart points={points} ghosts={ghosts} />);

    expect(container.querySelectorAll(".viz__fan-ghost")).toHaveLength(3);
    expect(screen.getByText("Run 0 · graine 10")).toBeInTheDocument();
    expect(screen.queryByText("Run 3 · graine 13")).not.toBeInTheDocument();
  });
});
