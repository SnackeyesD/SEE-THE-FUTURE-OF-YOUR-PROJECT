import type { Histogram, MonthlyAverage, SensitivityEntry } from "@see/protocol";
import { formatCurrency, formatNumber, formatPercent } from "../lib/format";

const CHART_WIDTH = 640;
const CHART_HEIGHT = 260;

function scale(value: number, min: number, max: number, start: number, end: number): number {
  if (max === min) return (start + end) / 2;
  return start + ((value - min) / (max - min)) * (end - start);
}

export function ProfitHistogram({
  histogram,
  currency,
  p10,
  p50,
  p90,
}: {
  histogram: Histogram;
  currency: string;
  p10: number;
  p50: number;
  p90: number;
}) {
  const bins = histogram.bins;
  if (bins.length === 0) return <p className="ui-muted">Aucune distribution disponible.</p>;
  const maxCount = Math.max(...bins.map((bin) => bin.count), 1);
  const min = bins[0].lower;
  const max = bins[bins.length - 1].upper;
  const left = 46;
  const right = CHART_WIDTH - 16;
  const top = 18;
  const bottom = CHART_HEIGHT - 34;
  const barWidth = (right - left) / bins.length;
  const markers = [
    { label: "P10", value: p10, color: "#f0b45a" },
    { label: "P50", value: p50, color: "#4f8cff" },
    { label: "P90", value: p90, color: "#3ecf8e" },
  ];
  return (
    <figure className="chart">
      <figcaption>
        <strong>Distribution du profit</strong>
        <span>Fréquence des résultats sur {formatNumber(bins.reduce((sum, bin) => sum + bin.count, 0))} simulations.</span>
      </figcaption>
      <svg
        viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
        role="img"
        aria-label="Histogramme de la distribution du profit avec les percentiles P10, P50 et P90"
      >
        <line x1={left} y1={bottom} x2={right} y2={bottom} className="chart__axis" />
        <line x1={left} y1={top} x2={left} y2={bottom} className="chart__axis" />
        {bins.map((bin, index) => {
          const height = ((bin.count / maxCount) * (bottom - top));
          return (
            <g key={`${bin.lower}-${index}`}>
              <rect
                x={left + index * barWidth + 1}
                y={bottom - height}
                width={Math.max(1, barWidth - 2)}
                height={height}
                className="chart__bar"
              >
                <title>
                  {formatCurrency(bin.lower, currency)} à {formatCurrency(bin.upper, currency)} :{" "}
                  {formatNumber(bin.count)} runs ({formatPercent(bin.probability)})
                </title>
              </rect>
            </g>
          );
        })}
        {markers.map((marker) => {
          const x = scale(marker.value, min, max, left, right);
          return (
            <g key={marker.label}>
              <line
                x1={x}
                y1={top}
                x2={x}
                y2={bottom}
                stroke={marker.color}
                strokeDasharray="4 4"
                strokeWidth={1.5}
              />
              <text x={x + 4} y={top + 12} fill={marker.color} className="chart__label">
                {marker.label} · {formatCurrency(marker.value, currency, { compact: true })}
              </text>
            </g>
          );
        })}
        <text x={left} y={CHART_HEIGHT - 10} className="chart__tick">
          {formatCurrency(min, currency, { compact: true })}
        </text>
        <text x={right} y={CHART_HEIGHT - 10} textAnchor="end" className="chart__tick">
          {formatCurrency(max, currency, { compact: true })}
        </text>
      </svg>
    </figure>
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
    .slice(0, 8);
  const max = Math.max(...top.map((entry) => Math.abs(entry.contribution)), 1e-9);
  const chartLeft = 220;
  const chartRight = CHART_WIDTH - 24;
  const center = (chartLeft + chartRight) / 2;
  const rowHeight = 25;
  const height = Math.max(CHART_HEIGHT, top.length * rowHeight + 48);
  return (
    <figure className="chart">
      <figcaption>
        <strong>Analyse de sensibilité</strong>
        <span>Contribution de chaque hypothèse à la variance du profit.</span>
      </figcaption>
      <svg
        viewBox={`0 0 ${CHART_WIDTH} ${height}`}
        role="img"
        aria-label="Diagramme tornade de la sensibilité du profit aux hypothèses"
      >
        <line x1={center} y1={18} x2={center} y2={height - 18} className="chart__axis" />
        {top.map((entry, index) => {
          const y = 28 + index * rowHeight;
          const width = (Math.abs(entry.contribution) / max) * ((chartRight - chartLeft) / 2);
          const positive = entry.contribution >= 0;
          return (
            <g key={entry.hypothesis}>
              <text x={chartLeft - 10} y={y + 12} textAnchor="end" className="chart__label">
                {entry.hypothesis}
              </text>
              <rect
                x={positive ? center : center - width}
                y={y}
                width={Math.max(2, width)}
                height={15}
                rx={3}
                className={positive ? "chart__bar chart__bar--positive" : "chart__bar chart__bar--negative"}
              >
                <title>
                  {entry.hypothesis}: contribution {formatCurrency(entry.contribution, currency, { compact: true })},
                  corrélation {entry.correlation.toFixed(2)}
                </title>
              </rect>
            </g>
          );
        })}
      </svg>
    </figure>
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
  const left = 48;
  const right = CHART_WIDTH - 20;
  const top = 22;
  const bottom = CHART_HEIGHT - 36;
  const profits = values.map((item) => item.meanProfit);
  const min = Math.min(0, ...profits);
  const max = Math.max(0, ...profits);
  const points = values.map((item, index) => {
    const x = values.length === 1 ? (left + right) / 2 : left + (index / (values.length - 1)) * (right - left);
    const y = scale(item.meanProfit, min, max, bottom, top);
    return { x, y, item };
  });
  const path = points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ");
  const zeroY = scale(0, min, max, bottom, top);
  return (
    <figure className="chart">
      <figcaption>
        <strong>Rentabilité mensuelle moyenne</strong>
        <span>Profit moyen par mois simulé, tous runs confondus.</span>
      </figcaption>
      <svg
        viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
        role="img"
        aria-label="Courbe du profit moyen par mois"
      >
        <line x1={left} y1={zeroY} x2={right} y2={zeroY} className="chart__zero" />
        <line x1={left} y1={top} x2={left} y2={bottom} className="chart__axis" />
        <path d={path} className="chart__line" />
        {points.map((point) => (
          <g key={point.item.index}>
            <circle cx={point.x} cy={point.y} r={3.5} className="chart__point">
              <title>
                Mois {point.item.month}: {formatCurrency(point.item.meanProfit, currency, { compact: true })}
              </title>
            </circle>
            {values.length <= 14 || point.item.index % 2 === 0 ? (
              <text x={point.x} y={CHART_HEIGHT - 12} textAnchor="middle" className="chart__tick">
                M{point.item.month}
              </text>
            ) : null}
          </g>
        ))}
        <text x={left + 6} y={top + 10} className="chart__tick">
          {formatCurrency(max, currency, { compact: true })}
        </text>
        <text x={left + 6} y={bottom - 4} className="chart__tick">
          {formatCurrency(min, currency, { compact: true })}
        </text>
      </svg>
    </figure>
  );
}
