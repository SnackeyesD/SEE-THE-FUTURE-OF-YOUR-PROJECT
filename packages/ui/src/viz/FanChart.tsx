import { useMemo, useRef, type KeyboardEvent, type PointerEvent } from "react";

import { leftPadFor, niceTicks, scale, serieStyle } from "./scale";
import {
  cdfProbabilityAt,
  fanBandPath,
  fanDomain,
  fanLinePath,
  normalizeFanPoints,
  thresholdStep,
  type CashCdfPoint,
  type FanPoint,
  type GhostSeries,
} from "./fan";

export type FanThreshold = {
  value: number;
  label: string;
  /** CDF fournie par le moteur ; `null` → « non disponible ». */
  cdf?: readonly CashCdfPoint[] | null;
  onChange?: (value: number) => void;
  onCommit?: (value: number) => void;
};

export type FanChartProps = {
  points: readonly FanPoint[];
  ghosts?: readonly GhostSeries[];
  threshold?: FanThreshold;
  selectedMonth?: number | null;
  onSelectMonth?: (month: number) => void;
  formatValue?: (value: number) => string;
  formatMonth?: (month: number) => string;
  formatProbability?: (probability: number) => string;
  title?: string;
  description?: string;
  width?: number;
  height?: number;
  ariaLabel?: string;
};

const MAX_GHOSTS = 3;

const PROBABILITY_FORMAT = new Intl.NumberFormat("fr-FR", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

function clamp(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) return min;
  return Math.min(Math.max(value, min), max);
}

/**
 * Éventail P10–P90 du cockpit : surface de fourchette, médiane, fantômes de
 * runs épinglés et seuil horizontal déplaçable. Les valeurs viennent du
 * moteur ; le seuil ne fait qu'interroger la CDF fournie.
 *
 * A11y : le seuil est un `slider` clavier (flèches, Page↑/↓, Home/End) et le
 * graphique expose un tableau repliable équivalent.
 */
export function FanChart({
  points,
  ghosts = [],
  threshold,
  selectedMonth = null,
  onSelectMonth,
  formatValue = (value) => String(value),
  formatMonth = (month) => `M${month}`,
  formatProbability = (probability) => `${PROBABILITY_FORMAT.format(probability * 100)} %`,
  title = "Éventail des résultats",
  description,
  width = 640,
  height = 300,
  ariaLabel,
}: FanChartProps) {
  const normalized = useMemo(() => normalizeFanPoints(points), [points]);
  const visibleGhosts = ghosts.slice(0, MAX_GHOSTS);
  const svgRef = useRef<SVGSVGElement | null>(null);

  const domain = useMemo(
    () =>
      fanDomain(
        normalized,
        visibleGhosts,
        threshold ? [threshold.value] : [],
      ),
    [normalized, threshold, visibleGhosts],
  );

  const yTicks = niceTicks(domain.min, domain.max, 4);
  const padLeft = leftPadFor(yTicks.map((tick) => formatValue(tick)));
  const padRight = 18;
  const padTop = 16;
  const padBottom = 30;
  const plotW = Math.max(10, width - padLeft - padRight);
  const plotH = Math.max(10, height - padTop - padBottom);

  const months = normalized.map((point) => point.month);
  const xMin = months[0] ?? 1;
  const xMax = months[months.length - 1] ?? 1;

  const xAt = (month: number) => scale(month, xMin, xMax, padLeft, padLeft + plotW);
  const yAt = (value: number) => scale(value, domain.min, domain.max, padTop + plotH, padTop);
  const project = (month: number, value: number): [number, number] => [
    xAt(month),
    yAt(value),
  ];

  const selectedPoint =
    selectedMonth === null
      ? null
      : normalized.find((point) => point.month === selectedMonth) ?? null;

  const thresholdProbability =
    threshold?.cdf !== undefined ? cdfProbabilityAt(threshold.cdf, threshold.value) : null;

  const xTickCount = Math.min(6, months.length);
  const xTicks: number[] = [];
  for (let index = 0; index < xTickCount; index += 1) {
    const position = Math.round((index / Math.max(1, xTickCount - 1)) * (months.length - 1));
    const tick = months[position];
    if (tick !== undefined) xTicks.push(tick);
  }

  const handleGraphKey = (event: KeyboardEvent<HTMLDivElement>): void => {
    if (!onSelectMonth || normalized.length === 0) return;
    const current = selectedMonth ?? normalized[0].month;
    if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
      event.preventDefault();
      const index = normalized.findIndex((point) => point.month === current);
      const next = index + (event.key === "ArrowRight" ? 1 : -1);
      const target = normalized[Math.min(Math.max(next, 0), normalized.length - 1)];
      if (target) onSelectMonth(target.month);
      return;
    }
    if (event.key === "Home") {
      event.preventDefault();
      onSelectMonth(normalized[0].month);
      return;
    }
    if (event.key === "End") {
      event.preventDefault();
      const last = normalized[normalized.length - 1];
      if (last) onSelectMonth(last.month);
    }
  };

  const beginThresholdDrag = (event: PointerEvent<SVGLineElement>): void => {
    if (!threshold?.onChange) return;
    event.preventDefault();
    let latest = threshold.value;
    const update = (clientY: number): void => {
      const svg = svgRef.current;
      const rect = svg?.getBoundingClientRect();
      if (!rect || rect.height <= 0) return;
      const viewY = ((clientY - rect.top) / rect.height) * height;
      const ratio = (padTop + plotH - viewY) / plotH;
      latest = clamp(
        domain.min + ratio * (domain.max - domain.min),
        domain.min,
        domain.max,
      );
      threshold.onChange?.(latest);
    };
    update(event.clientY);
    const move = (moveEvent: globalThis.PointerEvent): void => update(moveEvent.clientY);
    const stop = (): void => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
      window.removeEventListener("pointercancel", stop);
      threshold.onCommit?.(latest);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
    window.addEventListener("pointercancel", stop);
  };

  const handleThresholdKey = (event: KeyboardEvent<SVGLineElement>): void => {
    if (!threshold?.onChange) return;
    const step = thresholdStep(domain);
    const apply = (next: number): void => {
      const value = clamp(next, domain.min, domain.max);
      threshold.onChange?.(value);
      threshold.onCommit?.(value);
    };
    switch (event.key) {
      case "ArrowUp":
      case "ArrowRight":
        event.preventDefault();
        apply(threshold.value + step);
        break;
      case "ArrowDown":
      case "ArrowLeft":
        event.preventDefault();
        apply(threshold.value - step);
        break;
      case "PageUp":
        event.preventDefault();
        apply(threshold.value + step * 10);
        break;
      case "PageDown":
        event.preventDefault();
        apply(threshold.value - step * 10);
        break;
      case "Home":
        event.preventDefault();
        apply(domain.min);
        break;
      case "End":
        event.preventDefault();
        apply(domain.max);
        break;
      default:
        break;
    }
  };

  if (normalized.length === 0) {
    return (
      <figure className="viz">
        <figcaption className="viz__caption">
          <strong>{title}</strong>
          {description ? <span className="viz__desc">{description}</span> : null}
        </figcaption>
        <p className="viz__empty">Aucune bande P10–P90 disponible pour ce calcul.</p>
      </figure>
    );
  }

  return (
    <figure className="viz">
      <figcaption className="viz__caption">
        <strong>{title}</strong>
        {description ? <span className="viz__desc">{description}</span> : null}
      </figcaption>

      {visibleGhosts.length > 0 ? (
        <ul className="viz__fan-legend">
          {visibleGhosts.map((ghost, index) => (
            <li key={ghost.id}>
              <span
                className="viz__legend__chip"
                style={serieStyle(index + 1)}
                aria-hidden="true"
              />
              {`${ghost.label} · graine ${ghost.seed}`}
            </li>
          ))}
        </ul>
      ) : null}

      <div
        className="viz__fan-nav"
        role="group"
        tabIndex={0}
        aria-label={`${ariaLabel ?? title} — navigation clavier par mois`}
        onKeyDown={handleGraphKey}
      >
        <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={ariaLabel ?? title} ref={svgRef}>
          {yTicks.map((tick) => (
            <g key={tick}>
              <line
                className="viz__gridline"
                x1={padLeft}
                x2={padLeft + plotW}
                y1={yAt(tick)}
                y2={yAt(tick)}
              />
              <text
                className="viz__tick"
                x={padLeft - 6}
                y={yAt(tick) + 3}
                textAnchor="end"
              >
                {formatValue(tick)}
              </text>
            </g>
          ))}

          <line
            className="viz__axis"
            x1={padLeft}
            x2={padLeft + plotW}
            y1={yAt(domain.min)}
            y2={yAt(domain.min)}
          />
          {domain.min < 0 ? (
            <line
              className="viz__zero"
              x1={padLeft}
              x2={padLeft + plotW}
              y1={yAt(0)}
              y2={yAt(0)}
            />
          ) : null}

          {xTicks.map((tick) => (
            <text
              key={tick}
              className="viz__tick"
              x={xAt(tick)}
              y={height - 8}
              textAnchor="middle"
            >
              {formatMonth(tick)}
            </text>
          ))}

          <g className="viz__fan">
            <path className="viz__fan-band" d={fanBandPath(normalized, project)} />
            <path className="viz__fan-median" d={fanLinePath(normalized, "p50", project)} />
          </g>

          {visibleGhosts.map((ghost, index) => (
            <path
              key={ghost.id}
              className="viz__fan-ghost"
              style={serieStyle(index + 1)}
              d={fanLinePath(ghost.points, "p50", project)}
            >
              <title>{`${ghost.label} — graine ${ghost.seed}`}</title>
            </path>
          ))}

          {normalized.map((point) => (
            <rect
              key={point.month}
              className="viz__fan-hit"
              x={xAt(point.month) - Math.max(2, plotW / Math.max(1, normalized.length * 2))}
              y={padTop}
              width={Math.max(4, plotW / Math.max(1, normalized.length))}
              height={plotH}
              onClick={(event) => {
                if (onSelectMonth) {
                  event.stopPropagation();
                  onSelectMonth(point.month);
                }
              }}
            >
              <title>
                {`${formatMonth(point.month)} — P10 ${formatValue(point.p10)}, P50 ${formatValue(
                  point.p50,
                )}, P90 ${formatValue(point.p90)}`}
              </title>
            </rect>
          ))}

          {threshold ? (
            <g>
              <line
                className="viz__threshold"
                x1={padLeft}
                x2={padLeft + plotW}
                y1={yAt(threshold.value)}
                y2={yAt(threshold.value)}
              />
              <line
                className="viz__threshold-hit"
                data-testid="fan-threshold"
                role="slider"
                tabIndex={0}
                aria-label={threshold.label}
                aria-orientation="horizontal"
                aria-valuemin={domain.min}
                aria-valuemax={domain.max}
                aria-valuenow={threshold.value}
                aria-valuetext={`${formatValue(threshold.value)}${
                  thresholdProbability === null
                    ? " — probabilité non disponible"
                    : ` — ${formatProbability(thresholdProbability)}`
                }`}
                onPointerDown={beginThresholdDrag}
                onKeyDown={handleThresholdKey}
                x1={padLeft}
                x2={padLeft + plotW}
                y1={yAt(threshold.value)}
                y2={yAt(threshold.value)}
              />
              <text
                className="viz__threshold-label"
                x={padLeft + plotW}
                y={Math.max(12, yAt(threshold.value) - 6)}
                textAnchor="end"
              >
                {`${threshold.label} · ${formatValue(threshold.value)}${
                  thresholdProbability === null
                    ? " · non disponible"
                    : ` · ${formatProbability(thresholdProbability)}`
                }`}
              </text>
            </g>
          ) : null}

          {selectedPoint ? (
            <g>
              <line
                className="viz__crosshair"
                x1={xAt(selectedPoint.month)}
                x2={xAt(selectedPoint.month)}
                y1={padTop}
                y2={padTop + plotH}
              />
              {(
                [
                  ["p10", "viz__fan-dot"],
                  ["p50", "viz__fan-dot viz__fan-dot--ref"],
                  ["p90", "viz__fan-dot"],
                ] as const
              ).map(([key, className]) => (
                <circle
                  key={key}
                  className={className}
                  cx={xAt(selectedPoint.month)}
                  cy={yAt(selectedPoint[key])}
                  r={3}
                >
                  <title>{`${key.toUpperCase()} ${formatValue(selectedPoint[key])}`}</title>
                </circle>
              ))}
            </g>
          ) : null}
        </svg>
      </div>

      {selectedPoint ? (
        <p className="viz__fan-readout" aria-live="polite">
          {`${formatMonth(selectedPoint.month)} — P10 ${formatValue(
            selectedPoint.p10,
          )} · P50 ${formatValue(selectedPoint.p50)} · P90 ${formatValue(
            selectedPoint.p90,
          )}`}
        </p>
      ) : null}

      {thresholdProbability !== null && threshold ? (
        <p className="viz__fan-readout">
          {`P(trésorerie minimale < ${formatValue(threshold.value)}) = ${formatProbability(
            thresholdProbability,
          )}`}
        </p>
      ) : null}

      <details className="viz__table">
        <summary>Données du graphique</summary>
        <table>
          <thead>
            <tr>
              <th scope="col">Mois</th>
              <th scope="col">P10</th>
              <th scope="col">P50</th>
              <th scope="col">P90</th>
            </tr>
          </thead>
          <tbody>
            {normalized.map((point) => (
              <tr key={point.month}>
                <th scope="row">{formatMonth(point.month)}</th>
                <td>{formatValue(point.p10)}</td>
                <td>{formatValue(point.p50)}</td>
                <td>{formatValue(point.p90)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
