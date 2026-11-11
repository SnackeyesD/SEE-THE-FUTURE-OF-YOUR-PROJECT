import type { CSSProperties } from "react";

/**
 * Mise à l'échelle linéaire d'un domaine vers une plage de pixels.
 */
export function scale(value: number, min: number, max: number, start: number, end: number): number {
  if (max === min) return (start + end) / 2;
  return start + ((value - min) / (max - min)) * (end - start);
}

/**
 * Ticks « propres » (1/2/5 × 10^n) sur un domaine numérique.
 */
export function niceTicks(min: number, max: number, count = 4): number[] {
  if (max === min) return [min];
  const step0 = (max - min) / Math.max(1, count);
  const mag = Math.pow(10, Math.floor(Math.log10(step0)));
  const norm = step0 / mag;
  const step = (norm >= 5 ? 10 : norm >= 2.5 ? 5 : norm >= 1.5 ? 2 : 1) * mag;
  const start = Math.ceil(min / step) * step;
  const ticks: number[] = [];
  for (let v = start; v <= max + step * 1e-9; v += step) {
    ticks.push(Number(v.toFixed(10)));
  }
  return ticks;
}

/**
 * Style de série : pose les custom properties consommées par chart.css.
 * L'index est NORMALISÉ (modulo) — l'attribution stable par entité est du
 * ressort de l'appelant (le même scénario passe toujours le même index,
 * cf. standard-dataviz.md §attribution).
 */
export function serieStyle(index: number): CSSProperties {
  const i = ((index % 10) + 10) % 10;
  return {
    "--serie-color": `var(--series-${i + 1})`,
    "--serie-fill": `var(--series-${i + 1}-fill)`,
  } as CSSProperties;
}

/**
 * Padding gauche pour accueillir le tick y le plus long en mono 10px
 * (~6.1px par caractère + marge).
 */
export function leftPadFor(labels: string[], min = 44): number {
  const longest = labels.reduce((acc, label) => Math.max(acc, label.length), 0);
  return Math.max(min, Math.ceil(longest * 6.1) + 12);
}

/**
 * Domaine y incluant zéro (les mesures financières se lisent depuis 0).
 */
export function domainWithZero(values: number[]): { min: number; max: number } {
  const min = Math.min(0, ...values);
  const max = Math.max(0, ...values);
  return { min, max };
}
