import { scale } from "./scale";

export type DivergingRow = {
  label: string;
  value: number;
  /** Tooltip riche optionnel (ex. corrélation) — sinon « label : valeur ». */
  tooltip?: string;
};

/**
 * Barres divergentes horizontales (tornade de sensibilité) :
 * contributions positives/négatives différenciées (`--chart-positive` /
 * `--chart-negative`), ligne zéro pleine, valeurs mono au bout des barres,
 * libellés d'hypothèse à gauche. Le tri (impact décroissant) est du
 * ressort de l'appelant.
 */
export function DivergingBars({
  title,
  description,
  rows,
  formatValue,
  width = 640,
  rowHeight = 25,
  labelWidth = 220,
  ariaLabel,
}: {
  title: string;
  description?: string;
  rows: DivergingRow[];
  formatValue: (value: number) => string;
  width?: number;
  rowHeight?: number;
  labelWidth?: number;
  ariaLabel?: string;
}) {
  if (rows.length === 0) {
    return <p className="ui-muted">Aucune contribution disponible.</p>;
  }
  const height = rows.length * rowHeight + 44;
  const padTop = 22;
  const padBottom = 22;
  const chartLeft = labelWidth + 12;
  const chartRight = width - 24;
  const center = (chartLeft + chartRight) / 2;
  const halfWidth = (chartRight - chartLeft) / 2;
  const max = Math.max(...rows.map((row) => Math.abs(row.value)), 1e-9);
  const valueAt = (value: number) => scale(value, -max, max, center - halfWidth, center + halfWidth);

  return (
    <figure className="viz">
      <figcaption className="viz__caption">
        <strong>{title}</strong>
        {description ? <span className="viz__desc">{description}</span> : null}
      </figcaption>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={ariaLabel ?? title}>
        <line className="viz__axis" x1={center} x2={center} y1={padTop - 6} y2={height - padBottom + 6} />
        {rows.map((row, index) => {
          const y = padTop + index * rowHeight;
          const positive = row.value >= 0;
          const end = valueAt(row.value);
          const barStart = Math.min(center, end);
          const barWidth = Math.max(2, Math.abs(end - center));
          return (
            <g key={row.label}>
              <text className="viz__label" x={labelWidth} y={y + 12} textAnchor="end">
                {row.label}
              </text>
              <rect
                className={positive ? "viz__bar viz__bar--pos" : "viz__bar viz__bar--neg"}
                x={barStart}
                y={y}
                width={barWidth}
                height={15}
                rx={3}
              >
                <title>{row.tooltip ?? `${row.label} : ${formatValue(row.value)}`}</title>
              </rect>
              {/* valeur : côté opposé de la barre, sur encre — jamais
                  de collision avec les libellés d'hypothèses */}
              <text
                className="viz__barvalue"
                x={positive ? center - 6 : center + 6}
                y={y + 11}
                textAnchor={positive ? "end" : "start"}
              >
                {formatValue(row.value)}
              </text>
            </g>
          );
        })}
      </svg>
    </figure>
  );
}
