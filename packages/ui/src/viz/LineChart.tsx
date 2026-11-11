import { useMemo, useState } from "react";
import { Legend, type LegendItem } from "./Legend";
import { domainWithZero, leftPadFor, niceTicks, scale, serieStyle } from "./scale";

export type LinePoint = { x: number; y: number };

export type LineSeries = {
  /** Identité stable de l'entité (scénario) — ne change jamais entre rendus. */
  id: string;
  label: string;
  /** Index de série stable (attribution par entité, pas par ordre d'affichage). */
  seriesIndex: number;
  points: LinePoint[];
  /** Aire de distribution sous la ligne (single-série surtout). */
  area?: boolean;
};

/**
 * Courbes multi-séries « Ink & Signal » :
 * - grille hairline horizontale, axes sans cadre ;
 * - ticks y en mono tabulaire ;
 * - lignes 2px jointures rondes, points 3px à halo quand la densité le permet ;
 * - légende interactive (isoler une série) si `legend` et > 1 série.
 *
 * Performance : recevoir des séries AGRÉGÉES (le moteur simule 10 000 runs,
 * on n'affiche jamais les points bruts).
 */
export function LineChart({
  title,
  description,
  series,
  formatY = (value) => String(value),
  formatX = (value) => String(value),
  width = 640,
  height = 260,
  legend = false,
  ariaLabel,
}: {
  title: string;
  description?: string;
  series: LineSeries[];
  formatY?: (value: number) => string;
  formatX?: (value: number) => string;
  width?: number;
  height?: number;
  legend?: boolean;
  ariaLabel?: string;
}) {
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const visible = series.filter((serie) => !hidden.has(serie.id));

  // Domaine y : zéro inclus (lecture financière), séries visibles seulement.
  const yDomain = useMemo(() => {
    const values = visible.flatMap((serie) => serie.points.map((point) => point.y));
    if (values.length === 0) return { min: 0, max: 1 };
    return domainWithZero(values);
  }, [visible]);

  const xValues = visible
    .flatMap((serie) => serie.points.map((point) => point.x))
    .sort((a, b) => a - b);
  const xMin = xValues[0] ?? 0;
  const xMax = xValues[xValues.length - 1] ?? 1;

  const yTicks = niceTicks(yDomain.min, yDomain.max, 4);
  const padLeft = leftPadFor(yTicks.map((tick) => formatY(tick)));
  const padRight = 16;
  const padTop = 16;
  const padBottom = 30;
  const plotW = Math.max(10, width - padLeft - padRight);
  const plotH = Math.max(10, height - padTop - padBottom);

  const yAt = (value: number) => scale(value, yDomain.min, yDomain.max, padTop + plotH, padTop);
  const xAt = (value: number) => scale(value, xMin, xMax, padLeft, padLeft + plotW);
  const zeroY = yAt(0);
  const hasZeroLine = yDomain.min < 0 && yDomain.max > 0;

  // Points visibles seulement si la densité reste lisible.
  const totalPoints = visible.reduce((acc, serie) => acc + serie.points.length, 0);
  const showPoints = totalPoints <= 60;

  // Ticks x : ~6 positions réparties sur les abscisses réelles.
  const xTickCount = Math.min(6, xValues.length);
  const xTicks: number[] = [];
  if (xValues.length > 0) {
    for (let i = 0; i < xTickCount; i++) {
      const index = Math.round((i / Math.max(1, xTickCount - 1)) * (xValues.length - 1));
      xTicks.push(xValues[index]);
    }
  }

  const toggle = (id: string) => {
    setHidden((previous) => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const legendItems: LegendItem[] = series.map((serie) => ({
    id: serie.id,
    label: serie.label,
    seriesIndex: serie.seriesIndex,
  }));

  return (
    <figure className="viz">
      <figcaption className="viz__caption">
        <strong>{title}</strong>
        {description ? <span className="viz__desc">{description}</span> : null}
      </figcaption>
      {legend && series.length > 1 ? <Legend items={legendItems} hidden={hidden} onToggle={toggle} /> : null}
      {visible.length === 0 ? (
        <p className="viz__empty">Aucune série sélectionnée — cliquez sur la légende pour afficher.</p>
      ) : (
        <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={ariaLabel ?? title}>
          {/* grille horizontale (hairline) + ticks y */}
          {yTicks.map((tick) => (
            <g key={tick}>
              <line className="viz__gridline" x1={padLeft} x2={padLeft + plotW} y1={yAt(tick)} y2={yAt(tick)} />
              <text className="viz__tick" x={padLeft - 6} y={yAt(tick) + 3} textAnchor="end">
                {formatY(tick)}
              </text>
            </g>
          ))}
          {/* axe de base */}
          <line className="viz__axis" x1={padLeft} x2={padLeft + plotW} y1={yAt(yDomain.min)} y2={yAt(yDomain.min)} />
          {hasZeroLine ? <line className="viz__zero" x1={padLeft} x2={padLeft + plotW} y1={zeroY} y2={zeroY} /> : null}
          {/* ticks x */}
          {xTicks.map((tick) => (
            <text key={tick} className="viz__tick" x={xAt(tick)} y={height - 8} textAnchor="middle">
              {formatX(tick)}
            </text>
          ))}
          {/* séries : aire puis ligne puis points (ordre de superposition) */}
          {visible.map((serie) => {
            const style = serieStyle(serie.seriesIndex);
            const path = serie.points
              .map((point, index) => `${index === 0 ? "M" : "L"} ${xAt(point.x)} ${yAt(point.y)}`)
              .join(" ");
            const first = serie.points[0];
            const last = serie.points[serie.points.length - 1];
            if (!first || !last) return null;
            const areaPath = serie.area
              ? `${path} L ${xAt(last.x)} ${zeroY} L ${xAt(first.x)} ${zeroY} Z`
              : null;
            return (
              <g key={serie.id} style={style}>
                {areaPath ? <path className="viz__area" d={areaPath} /> : null}
                <path className="viz__line" d={path} />
                {showPoints
                  ? serie.points.map((point) => (
                      <circle key={point.x} className="viz__point" cx={xAt(point.x)} cy={yAt(point.y)} r={3}>
                        <title>
                          {serie.label} — {formatX(point.x)} : {formatY(point.y)}
                        </title>
                      </circle>
                    ))
                  : null}
              </g>
            );
          })}
        </svg>
      )}
    </figure>
  );
}
