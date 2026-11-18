import type { MonthlyAverage } from "@see/protocol";
import {
  FanChart,
  Tabs,
  type CashCdfPoint,
  type FanPoint,
  type GhostSeries,
} from "@see/ui";
import { useMemo } from "react";

import { formatCurrency, formatProbability } from "../../lib/format";

export type FanMode = "cash" | "profit";

const MODES = [
  { id: "cash", label: "Trésorerie" },
  { id: "profit", label: "Profit" },
];

/** Convertit les bandes mensuelles du moteur en points d'éventail. */
export function fanPointsFromMonthly(
  monthly: readonly MonthlyAverage[],
  mode: FanMode,
): FanPoint[] {
  const points: FanPoint[] = [];
  for (const entry of monthly) {
    const p10 = mode === "cash" ? entry.cashP10 : entry.profitP10;
    const p50 = mode === "cash" ? entry.cashP50 : entry.profitP50;
    const p90 = mode === "cash" ? entry.cashP90 : entry.profitP90;
    if (
      typeof p10 !== "number" ||
      typeof p50 !== "number" ||
      typeof p90 !== "number" ||
      !Number.isFinite(p10) ||
      !Number.isFinite(p50) ||
      !Number.isFinite(p90)
    ) {
      continue;
    }
    points.push({ month: entry.index, p10, p50, p90 });
  }
  return points;
}

/**
 * Éventail du cockpit : sélection trésorerie / profit, seuil de trésorerie
 * minimale et fantômes épinglés. La probabilité sous le seuil vient de la CDF
 * du moteur, jamais d'un recalcul.
 */
export function FanChartPanel({
  monthly,
  currency,
  cdf,
  mode,
  ghosts,
  threshold,
  selectedMonth,
  onModeChange,
  onThresholdChange,
  onSelectMonth,
}: {
  monthly: readonly MonthlyAverage[];
  currency: string;
  cdf?: readonly CashCdfPoint[] | null;
  mode: FanMode;
  ghosts?: readonly GhostSeries[];
  threshold: number;
  selectedMonth: number | null;
  onModeChange: (mode: FanMode) => void;
  onThresholdChange: (value: number, commit: boolean) => void;
  onSelectMonth: (month: number) => void;
}) {
  const points = useMemo(() => fanPointsFromMonthly(monthly, mode), [monthly, mode]);

  return (
    <section className="cockpit-fan" aria-label="Éventail des résultats">
      <Tabs
        items={MODES}
        value={mode}
        onChange={(id) => onModeChange(id === "profit" ? "profit" : "cash")}
        ariaLabel="Mesure affichée dans l'éventail"
      />

      {points.length === 0 ? (
        <p className="ui-muted">
          Bandes P10–P90 non disponibles pour cette mesure : lancez un calcul pour les obtenir.
        </p>
      ) : (
        <FanChart
          points={points}
          ghosts={mode === "cash" ? ghosts : []}
          threshold={
            mode === "cash"
              ? {
                  value: threshold,
                  label: "Trésorerie minimale",
                  cdf,
                  onChange: (value) => onThresholdChange(value, false),
                  onCommit: (value) => onThresholdChange(value, true),
                }
              : undefined
          }
          selectedMonth={selectedMonth}
          onSelectMonth={onSelectMonth}
          formatValue={(value) => formatCurrency(value, currency, { compact: true })}
          formatMonth={(month) => `M${month}`}
          formatProbability={(probability) => formatProbability(probability)}
          title={mode === "cash" ? "Trésorerie par mois" : "Profit par mois"}
          description={
            mode === "cash"
              ? "Bande P10–P90 de la trésorerie mensuelle. Le seuil interroge la CDF du moteur."
              : "Bande P10–P90 du profit mensuel, tous runs retenus."
          }
          ariaLabel={
            mode === "cash"
              ? "Éventail de trésorerie avec bande P10–P90, seuil de trésorerie minimale et fantômes"
              : "Éventail de profit avec bande P10–P90"
          }
        />
      )}
    </section>
  );
}
