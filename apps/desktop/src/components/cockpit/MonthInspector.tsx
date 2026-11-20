import type { MonthlyAverage, SimulationQuality } from "@see/protocol";
import { Badge, Histogram, Tabs, type VizBin } from "@see/ui";
import { useState } from "react";

import { formatCurrency, formatDateTime, formatNumber, formatProbability } from "../../lib/format";

type Measure = "profit" | "cash";

const MEASURES = [
  { id: "profit", label: "Profit" },
  { id: "cash", label: "Trésorerie" },
];

function toBins(
  histogram: MonthlyAverage["profitHistogram"] | MonthlyAverage["cashHistogram"],
): VizBin[] {
  return (histogram ?? []).map((bin) => ({
    lower: bin.lower,
    upper: bin.upper,
    count: bin.count,
    probability: bin.probability,
  }));
}

/**
 * Distribution de l'état au mois sélectionné.
 *
 * Les barres viennent exclusivement du résultat du moteur (histogrammes du
 * calcul final). Aucune distribution n'est inventée : sans données pour ce
 * mois, le composant l'explique et propose de relancer.
 */
export function MonthInspector({
  month,
  entry,
  currency,
  quality,
  seed,
  runs,
  computedAt,
  stale = false,
  onRelaunch,
}: {
  month: number | null;
  entry: MonthlyAverage | null;
  currency: string;
  quality: SimulationQuality | null;
  seed: number | null;
  runs?: number;
  computedAt?: string | null;
  stale?: boolean;
  onRelaunch?: () => void;
}) {
  const [measure, setMeasure] = useState<Measure>("profit");
  const bins = entry
    ? toBins(measure === "profit" ? entry.profitHistogram : entry.cashHistogram)
    : [];
  const percentiles = entry
    ? measure === "profit"
      ? ([
          { label: "P10", value: entry.profitP10 },
          { label: "P50", value: entry.profitP50 },
          { label: "P90", value: entry.profitP90 },
        ].filter((mark): mark is { label: string; value: number } =>
          typeof mark.value === "number",
        ))
      : ([
          { label: "P10", value: entry.cashP10 },
          { label: "P50", value: entry.cashP50 },
          { label: "P90", value: entry.cashP90 },
        ].filter((mark): mark is { label: string; value: number } =>
          typeof mark.value === "number",
        ))
    : [];

  return (
    <section className="cockpit-inspector" aria-label="Distribution du mois sélectionné">
      <div className="cockpit-inspector__head">
        <div>
          <strong>Mois {month ?? "—"}</strong>
          <span className="ui-muted">
            {quality ? (quality === "draft" ? " · brouillon" : " · final") : ""}
            {seed !== null ? ` · graine ${seed}` : ""}
            {runs ? ` · ${formatNumber(runs)} runs` : ""}
          </span>
        </div>
        <div className="ui-actions">
          {stale ? <Badge tone="warn">Périmé</Badge> : null}
          <span className="ui-muted" title={computedAt ?? undefined}>
            {computedAt ? formatDateTime(computedAt) : "non horodaté"}
          </span>
        </div>
      </div>

      <Tabs
        items={MEASURES}
        value={measure}
        onChange={(id) => setMeasure(id === "cash" ? "cash" : "profit")}
        ariaLabel="Mesure inspectée au mois sélectionné"
      />

      {!entry ? (
        <p className="ui-muted">Aucun résultat : lancez un calcul pour inspecter un mois.</p>
      ) : bins.length === 0 ? (
        <div className="cockpit-inspector__empty">
          <p className="ui-muted">
            Distribution non disponible pour le mois {month}.{" "}
            {quality === "draft"
              ? "Un brouillon ne transporte que les bandes P10–P90."
              : "Ce calcul ne contient pas les histogrammes mensuels."}
          </p>
          {onRelaunch ? (
            <button type="button" className="ui-link-like" onClick={onRelaunch}>
              Relancer un calcul final pour ce mois
            </button>
          ) : null}
        </div>
      ) : (
        <Histogram
          title={measure === "profit" ? "Profit du mois" : "Trésorerie du mois"}
          description={`Distribution sur ${formatNumber(runs ?? 0)} runs · point mort cumulé ${formatProbability(
            entry.breakEvenProbability,
          )}`}
          bins={bins}
          percentiles={percentiles}
          formatX={(value) => formatCurrency(value, currency, { compact: true })}
          formatTooltip={(bin) =>
            `${formatCurrency(bin.lower, currency, { compact: true })} → ${formatCurrency(
              bin.upper,
              currency,
              { compact: true },
            )} : ${formatNumber(bin.count)} runs`
          }
          height={200}
          ariaLabel={`Histogramme de ${
            measure === "profit" ? "profit" : "trésorerie"
          } du mois ${month}`}
        />
      )}
    </section>
  );
}
