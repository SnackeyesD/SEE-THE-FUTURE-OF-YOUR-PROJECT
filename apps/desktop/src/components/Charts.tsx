/**
 * Pont app ⇆ librairie viz (refont phase 04).
 * Traduit les types du protocole en props des composants `@see/ui/viz` :
 * - formats métier (FCFA, %) fournis en callbacks ;
 * - attribution de série STABLE par entité (standard-dataviz.md §attribution) ;
 * - aucune couleur : tout passe par les tokens via chart.css.
 */
import {
  DivergingBars,
  Histogram,
  LineChart,
  type VizBin,
} from "@see/ui";
import type { Histogram as ProtocolHistogram, MonthlyAverage, SensitivityEntry } from "@see/protocol";
import { formatCurrency, formatNumber } from "../lib/format";

export function ProfitHistogram({
  histogram,
  currency,
  p10,
  p50,
  p90,
}: {
  histogram: ProtocolHistogram;
  currency: string;
  p10: number;
  p50: number;
  p90: number;
}) {
  const bins: VizBin[] = histogram.bins;
  if (bins.length === 0) return <p className="ui-muted">Aucune distribution disponible.</p>;
  const runs = bins.reduce((sum, bin) => sum + bin.count, 0);
  return (
    <Histogram
      title="Distribution du profit"
      description={`Fréquence des résultats sur ${formatNumber(runs)} simulations.`}
      bins={bins}
      percentiles={[
        { label: "P10", value: p10 },
        { label: "P50", value: p50 },
        { label: "P90", value: p90 },
      ]}
      formatX={(value) => formatCurrency(value, currency, { compact: true })}
      ariaLabel="Histogramme de la distribution du profit avec les percentiles P10, P50 et P90"
    />
  );
}

export function SensitivityTornado({
  entries,
  currency,
}: {
  entries: SensitivityEntry[];
  currency: string;
}) {
  if (entries.length === 0) return <p className="ui-muted">Aucune sensibilité disponible.</p>;
  const top = [...entries]
    .sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution))
    .slice(0, 8)
    .map((entry) => ({
      label: entry.hypothesis,
      value: entry.contribution,
      tooltip: `corrélation ${entry.correlation.toFixed(2)}`,
    }));
  return (
    <DivergingBars
      title="Analyse de sensibilité"
      description="Contribution de chaque hypothèse à la variance du profit. Survolez une barre pour la corrélation."
      rows={top.map(({ label, value, tooltip }) => ({ label, value, tooltip }))}
      formatValue={(value) => formatCurrency(value, currency, { compact: true })}
      ariaLabel="Diagramme tornade de la sensibilité du profit aux hypothèses"
    />
  );
}

export function MonthlyProfitChart({
  values,
  currency,
}: {
  values: MonthlyAverage[];
  currency: string;
}) {
  if (values.length === 0) return <p className="ui-muted">Aucune projection mensuelle disponible.</p>;
  return (
    <LineChart
      title="Rentabilité mensuelle moyenne"
      description="Profit moyen par mois simulé, tous runs confondus."
      series={[
        {
          id: "profit-mensuel",
          label: "Profit moyen",
          // Série 1 : la mesure de référence de l'écran Résultats.
          seriesIndex: 0,
          area: true,
          points: values.map((item) => ({ x: item.index, y: item.meanProfit })),
        },
      ]}
      formatY={(value) => formatCurrency(value, currency, { compact: true })}
      formatX={(index) => {
        const item = values.find((candidate) => candidate.index === index);
        return item ? `M${item.month}` : `#${index}`;
      }}
      ariaLabel="Courbe du profit moyen par mois"
    />
  );
}
