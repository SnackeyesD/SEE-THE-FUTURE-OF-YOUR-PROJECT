import { leftPadFor, niceTicks, scale } from "./scale";

export type VizBin = {
  lower: number;
  upper: number;
  count: number;
  /** Probabilité du bin (0–1), optionnelle pour le tooltip. */
  probability?: number;
};

export type PercentileMark = {
  label: string;
  value: number;
};

/**
 * Histogramme de distribution « Ink & Signal » :
 * barres neutres (`--chart-bar`), grille hairline, ticks mono tabulaires,
 * percentiles marqués par lignes dashées — P50 seul prend la couleur
 * référence (série 1) : c'est LA mesure centrale, P10/P90 restent neutres.
 * Tooltip natif par bin (`<title>`), texte en mono.
 */
export function Histogram({
  title,
  description,
  bins,
  percentiles = [],
  formatX,
  formatTooltip,
  width = 640,
  height = 260,
  ariaLabel,
}: {
  title: string;
  description?: string;
  bins: VizBin[];
  percentiles?: PercentileMark[];
  formatX: (value: number) => string;
  /** Tooltip d'un bin : défaut « de X à Y : N runs ». */
  formatTooltip?: (bin: VizBin) => string;
  width?: number;
  height?: number;
  ariaLabel?: string;
}) {
  if (bins.length === 0) {
    return <p className="ui-muted">Aucune distribution disponible.</p>;
  }
  const maxCount = Math.max(...bins.map((bin) => bin.count), 1);
  const xMin = bins[0].lower;
  const xMax = bins[bins.length - 1].upper;

  const yTicks = niceTicks(0, maxCount, 3);
  const padLeft = leftPadFor(yTicks.map((tick) => String(tick)), 36);
  const padRight = 16;
  const padTop = 20;
  const padBottom = 30;
  const plotW = Math.max(10, width - padLeft - padRight);
  const plotH = Math.max(10, height - padTop - padBottom);
  const barWidth = plotW / bins.length;

  const xAt = (value: number) => scale(value, xMin, xMax, padLeft, padLeft + plotW);
  const yAt = (count: number) => scale(count, 0, maxCount, padTop + plotH, padTop);

  return (
    <figure className="viz">
      <figcaption className="viz__caption">
        <strong>{title}</strong>
        {description ? <span className="viz__desc">{description}</span> : null}
      </figcaption>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={ariaLabel ?? title}>
        {/* grille horizontale (fréquences) */}
        {yTicks
          .filter((tick) => tick > 0)
          .map((tick) => (
            <g key={tick}>
              <line className="viz__gridline" x1={padLeft} x2={padLeft + plotW} y1={yAt(tick)} y2={yAt(tick)} />
              <text className="viz__tick" x={padLeft - 6} y={yAt(tick) + 3} textAnchor="end">
                {tick}
              </text>
            </g>
          ))}
        <line className="viz__axis" x1={padLeft} x2={padLeft + plotW} y1={padTop + plotH} y2={padTop + plotH} />
        {bins.map((bin, index) => {
          const y = yAt(bin.count);
          const barHeight = padTop + plotH - y;
          const tooltip =
            formatTooltip ??
            ((b: VizBin) =>
              `${formatX(b.lower)} → ${formatX(b.upper)} : ${b.count} runs${b.probability !== undefined ? ` (${(b.probability * 100).toFixed(1)} %)` : ""}`);
          return (
            <rect
              key={`${bin.lower}-${index}`}
              className="viz__bar"
              x={padLeft + index * barWidth + 1}
              y={padTop + plotH - barHeight}
              width={Math.max(1, barWidth - 2)}
              height={Math.max(0, barHeight)}
              rx={2}
            >
              <title>{tooltip(bin)}</title>
            </rect>
          );
        })}
        {/* percentiles */}
        {percentiles.map((mark) => {
          if (mark.value < xMin || mark.value > xMax) return null;
          const isRef = mark.label === "P50";
          const x = xAt(mark.value);
          return (
            <g key={mark.label}>
              <line
                className={isRef ? "viz__pmark viz__pmark--ref" : "viz__pmark"}
                x1={x}
                x2={x}
                y1={padTop}
                y2={padTop + plotH}
              />
              <text
                className={isRef ? "viz__pmarklabel viz__pmarklabel--ref" : "viz__pmarklabel"}
                x={x + 4}
                y={padTop + 10}
              >
                {mark.label} · {formatX(mark.value)}
              </text>
            </g>
          );
        })}
        {/* bornes x */}
        <text className="viz__tick" x={padLeft} y={height - 8}>
          {formatX(xMin)}
        </text>
        <text className="viz__tick" x={padLeft + plotW} y={height - 8} textAnchor="end">
          {formatX(xMax)}
        </text>
      </svg>
    </figure>
  );
}
