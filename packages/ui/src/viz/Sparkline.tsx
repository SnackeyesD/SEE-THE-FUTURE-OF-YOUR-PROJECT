import { scale, serieStyle } from "./scale";

/**
 * Micro-ligne pour listes et stats — aperçu sans chart complet.
 * Pas d'axes, pas de ticks : la valeur exacte vit à côté (Stat, Table).
 * La série suit l'attribution stable de l'entité listée.
 */
export function Sparkline({
  values,
  seriesIndex = 0,
  width = 120,
  height = 28,
  ariaLabel,
}: {
  values: number[];
  seriesIndex?: number;
  width?: number;
  height?: number;
  ariaLabel: string;
}) {
  if (values.length < 2) return null;
  const pad = 3;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const xAt = (index: number) => scale(index, 0, values.length - 1, pad, width - pad);
  const yAt = (value: number) =>
    scale(value, min === max ? min - 1 : min, min === max ? max + 1 : max, height - pad, pad);
  const path = values
    .map((value, index) => `${index === 0 ? "M" : "L"} ${xAt(index)} ${yAt(value)}`)
    .join(" ");
  const lastIndex = values.length - 1;
  return (
    <svg
      className="viz__spark-svg"
      style={serieStyle(seriesIndex)}
      viewBox={`0 0 ${width} ${height}`}
      width={width}
      height={height}
      role="img"
      aria-label={ariaLabel}
    >
      <path className="viz__spark" d={path} />
      <circle className="viz__spark-dot" cx={xAt(lastIndex)} cy={yAt(values[lastIndex])} r={2} />
    </svg>
  );
}
