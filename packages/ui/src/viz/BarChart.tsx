import { domainWithZero, leftPadFor, niceTicks, scale, serieStyle } from "./scale";

export type BarCategory = {
  label: string;
  value: number;
  /** Index de série stable ; défaut = position (ordre du tableau). */
  seriesIndex?: number;
};

/**
 * Barres verticales de comparaison « Ink & Signal » — chaque catégorie
 * porte sa couleur de série (attribution stable), valeurs en mono au-dessus.
 * Positif/négatif reste lisible : la ligne zéro est dashée.
 */
export function BarChart({
  title,
  description,
  categories,
  formatValue,
  width = 640,
  height = 260,
  ariaLabel,
}: {
  title: string;
  description?: string;
  categories: BarCategory[];
  formatValue: (value: number) => string;
  width?: number;
  height?: number;
  ariaLabel?: string;
}) {
  if (categories.length === 0) {
    return <p className="ui-muted">Aucune comparaison disponible.</p>;
  }
  const values = categories.map((category) => category.value);
  const domain = domainWithZero(values);

  const yTicks = niceTicks(domain.min, domain.max, 4);
  const padLeft = leftPadFor(yTicks.map((tick) => formatValue(tick)));
  const padRight = 16;
  const padTop = 22;
  const padBottom = 34;
  const plotW = Math.max(10, width - padLeft - padRight);
  const plotH = Math.max(10, height - padTop - padBottom);
  const slotWidth = plotW / categories.length;
  const barWidth = Math.min(64, Math.max(8, slotWidth - 24));

  const yAt = (value: number) => scale(value, domain.min, domain.max, padTop + plotH, padTop);
  const zeroY = yAt(0);
  const hasNegative = domain.min < 0;

  return (
    <figure className="viz">
      <figcaption className="viz__caption">
        <strong>{title}</strong>
        {description ? <span className="viz__desc">{description}</span> : null}
      </figcaption>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={ariaLabel ?? title}>
        {yTicks
          .filter((tick) => tick !== 0)
          .map((tick) => (
            <g key={tick}>
              <line className="viz__gridline" x1={padLeft} x2={padLeft + plotW} y1={yAt(tick)} y2={yAt(tick)} />
              <text className="viz__tick" x={padLeft - 6} y={yAt(tick) + 3} textAnchor="end">
                {formatValue(tick)}
              </text>
            </g>
          ))}
        {hasNegative ? <line className="viz__zero" x1={padLeft} x2={padLeft + plotW} y1={zeroY} y2={zeroY} /> : null}
        <line className="viz__axis" x1={padLeft} x2={padLeft + plotW} y1={padTop + plotH} y2={padTop + plotH} />
        {categories.map((category, index) => {
          const center = padLeft + slotWidth * (index + 0.5);
          const y = yAt(Math.max(0, category.value));
          const barHeight = Math.abs(yAt(category.value) - zeroY);
          return (
            <g key={category.label} style={serieStyle(category.seriesIndex ?? index)}>
              <rect
                className="viz__bar viz__bar--serie"
                x={center - barWidth / 2}
                y={y}
                width={barWidth}
                height={Math.max(1, barHeight)}
                rx={3}
              >
                <title>
                  {category.label} : {formatValue(category.value)}
                </title>
              </rect>
              <text className="viz__barvalue" x={center} y={y - 6} textAnchor="middle">
                {formatValue(category.value)}
              </text>
              <text className="viz__label" x={center} y={height - 10} textAnchor="middle">
                {category.label}
              </text>
            </g>
          );
        })}
      </svg>
    </figure>
  );
}
