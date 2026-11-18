/**
 * Géométrie pure de l'éventail P10–P90 (phase 09).
 *
 * Aucune dépendance React ni métier : les tests de géométrie s'exécutent sans
 * DOM. Les valeurs restent celles du moteur ; ce module ne calcule jamais de
 * probabilité par simulation, il interpole seulement une CDF fournie.
 */

export type FanPoint = {
  month: number;
  p10: number;
  p50: number;
  p90: number;
};

export type GhostSeries = {
  id: string;
  label: string;
  points: FanPoint[];
  seed: number;
};

export type CashCdfPoint = {
  value: number;
  probability: number;
};

export type Domain = { min: number; max: number };

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

/** Trie par mois, copie les points et écarte les valeurs non finies. */
export function normalizeFanPoints(points: readonly FanPoint[]): FanPoint[] {
  return points
    .filter(
      (point) =>
        isFiniteNumber(point.month) &&
        isFiniteNumber(point.p10) &&
        isFiniteNumber(point.p50) &&
        isFiniteNumber(point.p90),
    )
    .map((point) => ({
      month: point.month,
      p10: point.p10,
      p50: point.p50,
      p90: point.p90,
    }))
    .sort((left, right) => left.month - right.month);
}

/**
 * Domaine vertical couvrant l'éventail, les fantômes et les valeurs annexes
 * (seuil). Zéro est inclus dès qu'une valeur est négative, pour que la ligne
 * zéro reste lisible ; un domaine entièrement négatif est remonté à zéro.
 */
export function fanDomain(
  points: readonly FanPoint[],
  ghosts: readonly GhostSeries[] = [],
  extras: readonly number[] = [],
): Domain {
  const values: number[] = [];
  for (const point of points) values.push(point.p10, point.p50, point.p90);
  for (const ghost of ghosts) {
    for (const point of ghost.points) values.push(point.p10, point.p50, point.p90);
  }
  for (const extra of extras) if (isFiniteNumber(extra)) values.push(extra);

  if (values.length === 0) return { min: 0, max: 1 };

  let min = Math.min(...values);
  let max = Math.max(...values);
  if (min < 0) min = Math.min(min, 0);
  if (max <= 0) max = 0;
  if (min === max) {
    const pad = Math.abs(min) * 0.1 || 1;
    min -= pad;
    max += pad;
  }
  return { min, max };
}

export type Projector = (month: number, value: number) => [number, number];

/** Surface P10–P90 : p90 à l'aller, p10 au retour, refermée. */
export function fanBandPath(points: readonly FanPoint[], project: Projector): string {
  const normalized = normalizeFanPoints(points);
  if (normalized.length < 2) return "";
  const upper = normalized.map((point) => {
    const [x, y] = project(point.month, point.p90);
    return `${x} ${y}`;
  });
  const lower = [...normalized].reverse().map((point) => {
    const [x, y] = project(point.month, point.p10);
    return `${x} ${y}`;
  });
  return `M ${upper.join(" L ")} L ${lower.join(" L ")} Z`;
}

/** Ligne d'un percentile (P50 par défaut). */
export function fanLinePath(
  points: readonly FanPoint[],
  percentile: "p10" | "p50" | "p90",
  project: Projector,
): string {
  const normalized = normalizeFanPoints(points);
  if (normalized.length === 0) return "";
  return normalized
    .map((point, index) => {
      const [x, y] = project(point.month, point[percentile]);
      return `${index === 0 ? "M" : "L"} ${x} ${y}`;
    })
    .join(" ");
}

/** Nettoie et trie une CDF (valeur → probabilité cumulée à droite). */
export function normalizeCdf(cdf: readonly CashCdfPoint[] | null | undefined): CashCdfPoint[] {
  if (!cdf || cdf.length === 0) return [];
  const deduped = new Map<number, number>();
  for (const point of cdf) {
    if (!isFiniteNumber(point.value) || !isFiniteNumber(point.probability)) continue;
    deduped.set(point.value, Math.min(1, Math.max(0, point.probability)));
  }
  return [...deduped.entries()]
    .map(([value, probability]) => ({ value, probability }))
    .sort((left, right) => left.value - right.value);
}

/**
 * P(min cash ≤ seuil) par interpolation linéaire entre deux points de CDF.
 * Retourne `null` sans CDF : l'appelant affiche « non disponible ».
 * Sous le premier point échantillonné la probabilité est 0, au-delà du
 * dernier elle vaut 1 (CDF empirique du run, jamais une extrapolation).
 */
export function cdfProbabilityAt(
  cdf: readonly CashCdfPoint[] | null | undefined,
  value: number,
): number | null {
  const points = normalizeCdf(cdf);
  if (points.length === 0) return null;
  if (!isFiniteNumber(value)) return null;

  const first = points[0];
  const last = points[points.length - 1];
  if (value < first.value) return 0;
  if (value >= last.value) return 1;

  let index = 1;
  while (index < points.length && points[index].value < value) index += 1;
  const current = points[index];
  const previous = points[index - 1];
  const span = current.value - previous.value;
  if (span <= 0) return current.probability;
  const ratio = (value - previous.value) / span;
  return previous.probability + ratio * (current.probability - previous.probability);
}

/** Point le plus proche d'un mois (sélection au clic / clavier). */
export function nearestMonth(
  points: readonly FanPoint[],
  month: number,
): number | null {
  const normalized = normalizeFanPoints(points);
  if (normalized.length === 0) return null;
  let best = normalized[0].month;
  let distance = Math.abs(best - month);
  for (const point of normalized) {
    const next = Math.abs(point.month - month);
    if (next < distance) {
      best = point.month;
      distance = next;
    }
  }
  return best;
}

/** Pas de clavier raisonnable pour un seuil monétaire (1 % du domaine). */
export function thresholdStep(domain: Domain): number {
  const span = Math.abs(domain.max - domain.min);
  if (!Number.isFinite(span) || span === 0) return 1;
  return span / 100;
}
