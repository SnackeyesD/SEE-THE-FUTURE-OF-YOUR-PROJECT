import type { SurfaceMetric } from "@see/protocol";
import { useMemo } from "react";

import { formatMetricAxis, formatMetricValue, surfaceMetricSpec } from "../../lib/metrics";

export type HeatmapRow = Array<number | null>;

const HEAT_STEPS = 5;

function clamp01(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.min(1, Math.max(0, value));
}

/**
 * Associe une valeur de cellule à un palier de couleur. Pour une métrique
 * « basse = meilleure » (point mort, perte), l'échelle est inversée : la
 * meilleure valeur prend le palier chaud, jamais une fausse lecture.
 */
export function heatColor(
  value: number,
  minimum: number,
  maximum: number,
  lowerIsBetter = false,
): string {
  if (!Number.isFinite(value)) return "var(--heat-empty)";
  const span = maximum - minimum;
  const ratio = span <= 0 ? 0.5 : clamp01((value - minimum) / span);
  const oriented = lowerIsBetter ? 1 - ratio : ratio;
  const step = Math.min(HEAT_STEPS - 1, Math.floor(oriented * HEAT_STEPS));
  return `var(--heat-${step})`;
}

export interface HeatmapProps {
  xValues: number[] | null;
  yValues: number[] | null;
  rows: HeatmapRow[];
  metric: SurfaceMetric;
  xLabel: string;
  yLabel: string;
  currency?: string;
  formatX?: (value: number) => string;
  formatY?: (value: number) => string;
  /** Point courant du scénario, fourni par le moteur (`result.current`). */
  current?: number[] | null;
  /** Applique les deux valeurs d'une cellule au scénario. */
  onApply?: (x: number, y: number) => void;
  applyLabel?: string;
}

/**
 * Carte de chaleur 2D orientée z[ligneY][colonneX].
 *
 * Aucun chiffre n'est recalculé : `rows` vient du moteur (lignes partielles ou
 * résultat final), et seules les couleurs et les libellés sont locaux.
 */
export function Heatmap({
  xValues,
  yValues,
  rows,
  metric,
  xLabel,
  yLabel,
  currency = "XOF",
  formatX,
  formatY,
  current,
  onApply,
  applyLabel = "Appliquer ces valeurs",
}: HeatmapProps) {
  const spec = surfaceMetricSpec(metric);
  const values = useMemo(() => {
    const flat: number[] = [];
    for (const row of rows) {
      for (const value of row) {
        if (value !== null && Number.isFinite(value)) flat.push(value);
      }
    }
    return flat;
  }, [rows]);

  const minimum = values.length > 0 ? Math.min(...values) : 0;
  const maximum = values.length > 0 ? Math.max(...values) : 0;

  const columns = rows[0]?.length ?? xValues?.length ?? 0;
  const rowCount = rows.length;
  const complete = rows.every((row) => row.every((value) => value !== null));

  const labelForX = (value: number | undefined, index: number): string => {
    if (value === undefined) return `#${index + 1}`;
    return formatX ? formatX(value) : formatMetricAxis(metric, value);
  };
  const labelForY = (value: number | undefined, index: number): string => {
    if (value === undefined) return `#${index + 1}`;
    return formatY ? formatY(value) : formatMetricAxis(metric, value);
  };

  if (columns === 0 || rowCount === 0) {
    return (
      <p className="ui-muted" role="status">
        En attente des premiers points du moteur…
      </p>
    );
  }

  const isCurrent = (xIndex: number, yIndex: number): boolean => {
    if (!current) return false;
    const x = xValues?.[xIndex];
    const y = yValues?.[yIndex];
    return x !== undefined && y !== undefined && current[0] === x && current[1] === y;
  };

  return (
    <figure className="heatmap" aria-label={`Surface ${xLabel} × ${yLabel}`}>
      <figcaption className="heatmap__caption">
        <strong>
          {spec.label} selon {xLabel} (colonnes) et {yLabel} (lignes)
        </strong>
        <span className="ui-muted">
          {complete
            ? "Valeurs du moteur, mêmes tirages pour chaque cellule."
            : `Calcul en cours — ${rows.reduce(
                (count, row) => count + row.filter((value) => value !== null).length,
                0,
              )} / ${columns * rowCount} cellules.`}
        </span>
      </figcaption>

      <div
        className="heatmap__grid"
        role="grid"
        aria-label={`${spec.label} : ${yLabel} en lignes, ${xLabel} en colonnes`}
        style={{ gridTemplateColumns: `minmax(4.5rem, auto) repeat(${columns}, minmax(2.25rem, 1fr))` }}
      >
        <div className="heatmap__corner" aria-hidden="true">
          {yLabel} \ {xLabel}
        </div>
        {Array.from({ length: columns }, (_, xIndex) => (
          <div key={`x-${xIndex}`} className="heatmap__axis heatmap__axis--x" role="columnheader">
            {labelForX(xValues?.[xIndex], xIndex)}
          </div>
        ))}

        {rows.map((row, yIndex) => (
          <div key={`row-${yIndex}`} className="heatmap__row" role="row" style={{ display: "contents" }}>
            <div className="heatmap__axis heatmap__axis--y" role="rowheader">
              {labelForY(yValues?.[yIndex], yIndex)}
            </div>
            {Array.from({ length: columns }, (_, xIndex) => {
              const value = row[xIndex] ?? null;
              const x = xValues?.[xIndex];
              const y = yValues?.[yIndex];
              const readable =
                value === null
                  ? "en attente"
                  : formatMetricValue(metric, value, currency);
              const title =
                value === null
                  ? `${xLabel} ${labelForX(x, xIndex)} · ${yLabel} ${labelForY(
                      y,
                      yIndex,
                    )} : en attente`
                  : `${xLabel} ${labelForX(x, xIndex)} · ${yLabel} ${labelForY(
                      y,
                      yIndex,
                    )} : ${readable}`;
              const selected = isCurrent(xIndex, yIndex);
              return (
                <button
                  key={`cell-${yIndex}-${xIndex}`}
                  type="button"
                  role="gridcell"
                  className={
                    selected ? "heatmap__cell heatmap__cell--current" : "heatmap__cell"
                  }
                  style={{
                    background:
                      value === null
                        ? "var(--heat-empty)"
                        : heatColor(value, minimum, maximum, spec.lowerIsBetter),
                  }}
                  title={title}
                  aria-label={title}
                  aria-current={selected ? "true" : undefined}
                  disabled={value === null || !onApply || x === undefined || y === undefined}
                  onClick={() => {
                    if (!onApply || x === undefined || y === undefined) return;
                    onApply(x, y);
                  }}
                >
                  <span className="heatmap__value">
                    {value === null ? "" : formatMetricAxis(metric, value)}
                  </span>
                </button>
              );
            })}
          </div>
        ))}
      </div>

      <div className="heatmap__footer">
        <div className="heatmap__legend" aria-hidden="true">
          {Array.from({ length: HEAT_STEPS }, (_, index) => (
            <span
              key={index}
              className="heatmap__swatch"
              style={{ background: `var(--heat-${index})` }}
            />
          ))}
        </div>
        <span className="heatmap__range">
          {values.length === 0
            ? "—"
            : `${formatMetricValue(metric, minimum, currency)} → ${formatMetricValue(
                metric,
                maximum,
                currency,
              )}`}
        </span>
        {onApply ? (
          <span className="ui-muted">{applyLabel} : cliquez une cellule.</span>
        ) : null}
      </div>

      {!complete ? (
        <p className="ui-muted" role="status">
          Les cellules vides seront remplies par le moteur, jamais estimées ici.
        </p>
      ) : null}
    </figure>
  );
}
