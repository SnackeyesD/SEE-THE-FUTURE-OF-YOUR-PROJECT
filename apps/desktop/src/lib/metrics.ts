import type { SurfaceMetric } from "@see/protocol";

import { formatNumber, formatProbability } from "./format";

export type SurfaceMetricFormat = "currency" | "months" | "probability";

export interface SurfaceMetricSpec {
  key: SurfaceMetric;
  label: string;
  /** Unité affichée dans les tooltips et la légende. */
  unit: string;
  format: SurfaceMetricFormat;
  /** `true` quand une valeur basse est la meilleure (ex. point mort). */
  lowerIsBetter: boolean;
}

/**
 * Catalogue des métriques exposées par la surface et la recherche d'objectif.
 * Les clés sont celles du protocole ; aucune valeur n'est calculée ici.
 */
export const SURFACE_METRICS: SurfaceMetricSpec[] = [
  {
    key: "profit_p50",
    label: "Profit médian",
    unit: "FCFA",
    format: "currency",
    lowerIsBetter: false,
  },
  {
    key: "profit_p10",
    label: "Profit P10 (pessimiste)",
    unit: "FCFA",
    format: "currency",
    lowerIsBetter: false,
  },
  {
    key: "profit_p90",
    label: "Profit P90 (optimiste)",
    unit: "FCFA",
    format: "currency",
    lowerIsBetter: false,
  },
  {
    key: "break_even_months_p50",
    label: "Point mort médian",
    unit: "mois",
    format: "months",
    lowerIsBetter: true,
  },
  {
    key: "financing_need_p90",
    label: "Besoin de financement P90",
    unit: "FCFA",
    format: "currency",
    lowerIsBetter: true,
  },
  {
    key: "loss_probability",
    label: "Probabilité de perte",
    unit: "%",
    format: "probability",
    lowerIsBetter: true,
  },
];

export const SURFACE_METRIC_BY_KEY = new Map<SurfaceMetric, SurfaceMetricSpec>(
  SURFACE_METRICS.map((spec) => [spec.key, spec]),
);

export function surfaceMetricSpec(key: SurfaceMetric): SurfaceMetricSpec {
  return SURFACE_METRIC_BY_KEY.get(key) ?? SURFACE_METRICS[0];
}

/** Formate une valeur de métrique sans jamais inventer d'unité. */
export function formatMetricValue(
  key: SurfaceMetric,
  value: number,
  currency = "XOF",
): string {
  const spec = surfaceMetricSpec(key);
  if (spec.format === "probability") return formatProbability(value);
  if (spec.format === "months") {
    if (!Number.isFinite(value)) return "non atteint";
    const rounded = Number.isInteger(value) ? value : value.toFixed(1);
    return `${rounded} mois`;
  }
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: /^[A-Za-z]{3}$/.test(currency) ? currency.toUpperCase() : "XOF",
    maximumFractionDigits: currency === "XOF" || currency === "XAF" ? 0 : 2,
    notation: Math.abs(value) >= 100_000 ? "compact" : "standard",
  }).format(value);
}

/** Pourcentage court, sans le préfixe « ≥ » des probabilités bornées. */
export function formatMetricAxis(key: SurfaceMetric, value: number): string {
  const spec = surfaceMetricSpec(key);
  if (spec.format === "probability") return formatNumber(value * 100, 0) + " %";
  if (spec.format === "months") return `${formatNumber(value, 0)} m`;
  return new Intl.NumberFormat("fr-FR", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}
