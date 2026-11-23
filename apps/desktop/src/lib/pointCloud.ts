/**
 * Nuage Monte Carlo 3D.
 *
 * Les seules données par run autorisées passent par `simulation.trajectories`
 * (phase 12, borné à 200 trajectoires). Ce module agrège ces trajectoires en
 * points : besoin de financement (axe X), mois de point mort (axe Y) et profit
 * final (axe Z). Aucune simulation n'est relancée.
 */

import type { Trajectory } from "@see/protocol";

import { heatStep, normalizedAxis } from "./surface3d";

export interface PointCloudInput {
  trajectories: Trajectory[];
  horizonMonths: number;
}

export interface PointCloudPoint {
  index: number;
  financingNeed: number;
  breakEvenMonth: number | null;
  finalProfit: number;
  minimumCash: number;
}

export interface PointCloudGeometry {
  points: PointCloudPoint[];
  positions: Float32Array;
  /** Palier de couleur 0..4 par point, `MISSING_CELL` jamais utilisé ici. */
  heatSteps: Uint8Array;
  minimumProfit: number;
  maximumProfit: number;
  maximumFinancingNeed: number;
  horizonMonths: number;
}

/** Profit cumulé mois par mois (le dernier élément = profit final). */
export function cumulativeProfit(profitMonthly: number[]): number[] {
  let total = 0;
  return profitMonthly.map((value) => {
    total += Number.isFinite(value) ? value : 0;
    return total;
  });
}

/**
 * Premier mois (1-based) où le profit cumulé devient positif ou nul.
 * `null` si le point mort n'est pas atteint sur l'horizon.
 */
export function breakEvenMonth(cumulative: number[]): number | null {
  for (let index = 0; index < cumulative.length; index += 1) {
    if (cumulative[index] >= 0) return index + 1;
  }
  return null;
}

function normalizeExtent(value: number, minimum: number, maximum: number): number {
  const span = maximum - minimum;
  if (span <= 0) return 0;
  return Math.min(1, Math.max(0, (value - minimum) / span)) * 2 - 1;
}

export function buildPointCloud(input: PointCloudInput): PointCloudGeometry {
  const horizonMonths = Math.max(1, input.horizonMonths);
  const points: PointCloudPoint[] = [];

  for (const trajectory of input.trajectories) {
    if (!Array.isArray(trajectory.profitMonthly) || trajectory.profitMonthly.length === 0) {
      continue;
    }
    const cumulative = cumulativeProfit(trajectory.profitMonthly);
    const finalProfit = cumulative[cumulative.length - 1] ?? 0;
    const cash = Array.isArray(trajectory.cashMonthly) ? trajectory.cashMonthly : [];
    const minimumCash =
      cash.length > 0
        ? Math.min(...cash.filter((value) => Number.isFinite(value)))
        : 0;
    points.push({
      index: trajectory.index,
      financingNeed: Math.max(0, -minimumCash),
      breakEvenMonth: breakEvenMonth(cumulative),
      finalProfit,
      minimumCash,
    });
  }

  const positions = new Float32Array(points.length * 3);
  const heatSteps = new Uint8Array(points.length);
  const profits = points.map((point) => point.finalProfit);
  const minimumProfit = profits.length > 0 ? Math.min(...profits) : 0;
  const maximumProfit = profits.length > 0 ? Math.max(...profits) : 0;
  const maximumFinancingNeed =
    points.length > 0 ? Math.max(...points.map((point) => point.financingNeed)) : 0;

  points.forEach((point, position) => {
    const x = normalizeExtent(point.financingNeed, 0, Math.max(maximumFinancingNeed, 1e-9));
    const y =
      point.breakEvenMonth === null
        ? normalizedAxis(horizonMonths, horizonMonths)
        : normalizedAxis(point.breakEvenMonth - 1, horizonMonths);
    const z = normalizeExtent(point.finalProfit, minimumProfit, maximumProfit);
    positions[position * 3] = x;
    positions[position * 3 + 1] = y;
    positions[position * 3 + 2] = z;
    heatSteps[position] = heatStep(
      point.finalProfit,
      minimumProfit,
      maximumProfit,
      false,
    );
  });

  return {
    points,
    positions,
    heatSteps,
    minimumProfit,
    maximumProfit,
    maximumFinancingNeed,
    horizonMonths,
  };
}
