import type { MonthlyAverage } from "@see/protocol";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { simulationResult } from "../../test/fixtures";
import { KpiBar } from "./KpiBar";

/** Le mois est désormais contrôlé par l'écran : le test fournit un harnais. */
function ControlledKpi({
  initialMonth = 12,
  ...props
}: Omit<Parameters<typeof KpiBar>[0], "month" | "onMonthChange"> & {
  initialMonth?: number;
}) {
  const [month, setMonth] = useState<number | null>(initialMonth);
  return <KpiBar {...props} month={month} onMonthChange={setMonth} />;
}

function month(index: number, breakEvenProbability: number | null): MonthlyAverage {
  return {
    index,
    month: ((index - 1) % 12) + 1,
    meanRevenue: 100_000,
    meanProfit: 20_000,
    meanDemand: 500,
    meanUnitsSold: 480,
    meanStockEnd: 100,
    stockoutProbability: 0.05,
    profitP10: 5_000,
    profitP50: 20_000,
    profitP90: 40_000,
    cashP10: 100_000,
    cashP50: 200_000,
    cashP90: 300_000,
    breakEvenProbability,
  };
}

const monthly = Array.from({ length: 12 }, (_, index) =>
  month(index + 1, index === 5 ? 0.4 : index === 11 ? 0.9 : 0.7),
);

describe("KpiBar", () => {
  it("affiche les KPI du moteur et la graine", () => {
    render(
      <ControlledKpi
        currency="XOF"
        metrics={simulationResult.metrics}
        monthly={monthly}
        convergence={{ converged: true, stability: 1, maxRelativeChange: 0, stableBlocks: 3 }}
        status="idle"
        quality="final"
        seed={42}
        runs={10_000}
        runsRetained={9_800}
        engineVersion="0.2.0"
        onSeedChange={() => undefined}
      />,
    );

    expect(screen.getByText("Convergé")).toBeInTheDocument();
    expect(screen.getByText("Final")).toBeInTheDocument();
    expect(screen.getByText("moteur 0.2.0")).toBeInTheDocument();
    expect(screen.getByLabelText("Graine")).toHaveValue(42);
    expect(screen.getByLabelText("Point mort ≤")).toHaveValue("12");
    expect(screen.getAllByText(/9\s?800 \/ 10\s?000 runs/).length).toBeGreaterThan(0);
  });

  it("lit la probabilité cumulée au mois choisi", () => {
    render(
      <ControlledKpi
        currency="XOF"
        metrics={simulationResult.metrics}
        monthly={monthly}
        status="idle"
        seed={42}
        onSeedChange={() => undefined}
      />,
    );

    expect(screen.getByText(/90\s?%/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Point mort ≤"), { target: { value: "6" } });
    expect(screen.getByText(/40\s?%/)).toBeInTheDocument();
  });

  it("accepte un mois arbitraire venu du curseur de temps", () => {
    render(
      <ControlledKpi
        initialMonth={7}
        currency="XOF"
        metrics={simulationResult.metrics}
        monthly={monthly}
        status="idle"
        seed={42}
        onSeedChange={() => undefined}
      />,
    );

    const kpi = screen.getByRole("region", { name: "Indicateurs clés" });
    expect(within(kpi).getByLabelText("Point mort ≤")).toHaveValue("7");
    // month(7) porte une probabilité de 0,7 : elle ne doit pas être
    // remplacée par celle de l'horizon (0,9).
    expect(within(kpi).getByText(/70\s?%/)).toBeInTheDocument();
  });

  it("affiche « non disponible » sans agrégats", () => {
    render(
      <ControlledKpi
        currency="XOF"
        metrics={null}
        monthly={[]}
        status="idle"
        seed={7}
        onSeedChange={() => undefined}
      />,
    );

    expect(screen.getAllByText("non disponible").length).toBeGreaterThanOrEqual(3);
    expect(screen.getByText("Convergence inconnue")).toBeInTheDocument();
  });

  it("signale une stabilité partielle pendant un calcul", () => {
    render(
      <ControlledKpi
        currency="XOF"
        metrics={simulationResult.metrics}
        monthly={monthly}
        convergence={{ converged: false, stability: 0.66, maxRelativeChange: 0.012, stableBlocks: 1 }}
        status="drafting"
        seed={42}
        onSeedChange={() => undefined}
      />,
    );
    expect(screen.getByText("Stabilisation 66 %")).toBeInTheDocument();
  });

  it("remonte les changements de graine", () => {
    const onSeedChange = vi.fn();
    render(
      <ControlledKpi
        currency="XOF"
        metrics={null}
        monthly={[]}
        status="idle"
        seed={42}
        onSeedChange={onSeedChange}
      />,
    );

    fireEvent.change(screen.getByLabelText("Graine"), { target: { value: "777" } });
    expect(onSeedChange).toHaveBeenCalledWith(777);
  });
});
