/**
 * Spécifications des hypothèses du modèle `retail_depot`.
 *
 * Source unique partagée par l'écran Hypothèses (formulaire complet) et le
 * cockpit (poignées min/mode/max). Unités et bornes sont descriptives : le
 * moteur reste l'autorité de validation.
 */

export type AssumptionGroup = "prix" | "couts" | "demande" | "stock" | "finance";

export interface AssumptionSpec {
  key: string;
  label: string;
  unit: string;
  defaultValue: number;
  required: boolean;
  min?: number;
  max?: number;
  group: AssumptionGroup;
}

export const ASSUMPTION_GROUPS: Array<{ id: AssumptionGroup; label: string }> = [
  { id: "prix", label: "Prix" },
  { id: "couts", label: "Coûts" },
  { id: "demande", label: "Demande" },
  { id: "stock", label: "Stock" },
  { id: "finance", label: "Finance" },
];

export const ASSUMPTION_SPECS: AssumptionSpec[] = [
  {
    key: "initial_cash",
    label: "Trésorerie initiale",
    unit: "FCFA",
    defaultValue: 500_000,
    required: true,
    min: 0,
    group: "finance",
  },
  {
    key: "unit_price",
    label: "Prix de vente unitaire",
    unit: "FCFA/unité",
    defaultValue: 5_000,
    required: true,
    min: 0,
    group: "prix",
  },
  {
    key: "unit_cost",
    label: "Coût d'achat unitaire",
    unit: "FCFA/unité",
    defaultValue: 3_000,
    required: true,
    min: 0,
    group: "couts",
  },
  {
    key: "fixed_costs_monthly",
    label: "Coûts fixes mensuels",
    unit: "FCFA/mois",
    defaultValue: 300_000,
    required: true,
    min: 0,
    group: "couts",
  },
  {
    key: "demand_mean_monthly",
    label: "Demande moyenne mensuelle",
    unit: "unités/mois",
    defaultValue: 200,
    required: true,
    min: 0,
    group: "demande",
  },
  {
    key: "demand_cv",
    label: "Variation de la demande",
    unit: "coefficient",
    defaultValue: 0.2,
    required: false,
    min: 0,
    max: 5,
    group: "demande",
  },
  {
    key: "loss_rate",
    label: "Taux de perte mensuel",
    unit: "fraction",
    defaultValue: 0.02,
    required: false,
    min: 0,
    max: 1,
    group: "stock",
  },
  {
    key: "logistics_cost_per_unit",
    label: "Coût logistique unitaire",
    unit: "FCFA/unité",
    defaultValue: 0,
    required: false,
    min: 0,
    group: "couts",
  },
  {
    key: "target_stock_months",
    label: "Stock cible",
    unit: "mois de demande",
    defaultValue: 1,
    required: false,
    min: 0,
    max: 24,
    group: "stock",
  },
  {
    key: "reorder_lead_time_months",
    label: "Délai de réapprovisionnement",
    unit: "mois",
    defaultValue: 1,
    required: false,
    min: 0,
    max: 24,
    group: "stock",
  },
  {
    key: "initial_stock",
    label: "Stock initial",
    unit: "unités",
    defaultValue: 0,
    required: false,
    min: 0,
    group: "stock",
  },
  {
    key: "tax_rate",
    label: "Taux d'imposition",
    unit: "fraction",
    defaultValue: 0,
    required: false,
    min: 0,
    max: 1,
    group: "finance",
  },
];

export const ASSUMPTION_BY_KEY: ReadonlyMap<string, AssumptionSpec> = new Map(
  ASSUMPTION_SPECS.map((spec) => [spec.key, spec]),
);

export function assumptionLabel(key: string): string {
  return ASSUMPTION_BY_KEY.get(key)?.label ?? key;
}

export function assumptionUnit(key: string): string {
  return ASSUMPTION_BY_KEY.get(key)?.unit ?? "";
}
