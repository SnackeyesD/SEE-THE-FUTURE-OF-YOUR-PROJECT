// AUTO-GENERATED FILE — DO NOT EDIT BY HAND.
// Source: packages/engine/engine/events.py (EVENT_CATALOG)
// Regenerate with: npm run catalog:generate
import type { DistributionSpec, ScenarioEvent } from "./generated";

export type EventType = ScenarioEvent["type"];

export type EventCatalogTarget = {
  id: string;
  label: string;
};

export type EventCatalogEntry = {
  type: EventType;
  label: string;
  description: string;
  target: string;
  targetLabel: string;
  mode: "multiplicative" | "additive";
  allowedTargets: EventCatalogTarget[];
  defaultMagnitude: DistributionSpec;
};

export const EVENT_CATALOG: EventCatalogEntry[] = [
  {
    "type": "supplier_price_rise",
    "label": "Hausse du prix fournisseur",
    "description": "Le coût d'achat augmente de 5 à 30 % pendant la fenêtre.",
    "target": "unit_cost",
    "targetLabel": "Coût d'achat unitaire",
    "mode": "multiplicative",
    "allowedTargets": [
      {
        "id": "logistics_cost_per_unit",
        "label": "Coût logistique unitaire"
      },
      {
        "id": "unit_cost",
        "label": "Coût d'achat unitaire"
      }
    ],
    "defaultMagnitude": {
      "kind": "triangular",
      "low": 1.05,
      "mode": 1.15,
      "high": 1.3
    }
  },
  {
    "type": "supply_disruption",
    "label": "Rupture d'approvisionnement",
    "description": "Le délai de livraison s'allonge de 1 à 4 mois (ou les pertes augmentent).",
    "target": "reorder_lead_time_months",
    "targetLabel": "Délai de réapprovisionnement",
    "mode": "additive",
    "allowedTargets": [
      {
        "id": "loss_rate",
        "label": "Taux de perte mensuel"
      },
      {
        "id": "reorder_lead_time_months",
        "label": "Délai de réapprovisionnement"
      }
    ],
    "defaultMagnitude": {
      "kind": "triangular",
      "low": 1.0,
      "mode": 2.0,
      "high": 4.0
    }
  },
  {
    "type": "competitor_entry",
    "label": "Arrivée d'un concurrent",
    "description": "La demande baisse de 5 à 30 % pendant la fenêtre.",
    "target": "demand_mean_monthly",
    "targetLabel": "Demande moyenne mensuelle",
    "mode": "multiplicative",
    "allowedTargets": [
      {
        "id": "demand_mean_monthly",
        "label": "Demande moyenne mensuelle"
      }
    ],
    "defaultMagnitude": {
      "kind": "triangular",
      "low": 0.7,
      "mode": 0.85,
      "high": 0.95
    }
  },
  {
    "type": "power_outage",
    "label": "Coupure d'électricité prolongée",
    "description": "Les pertes de stock augmentent de 1 à 5 points par mois.",
    "target": "loss_rate",
    "targetLabel": "Taux de perte mensuel",
    "mode": "additive",
    "allowedTargets": [
      {
        "id": "fixed_costs_monthly",
        "label": "Coûts fixes mensuels"
      },
      {
        "id": "loss_rate",
        "label": "Taux de perte mensuel"
      }
    ],
    "defaultMagnitude": {
      "kind": "uniform",
      "low": 0.01,
      "high": 0.05
    }
  },
  {
    "type": "fx_shock",
    "label": "Choc de change",
    "description": "La logistique augmente de 3 à 15 % pendant la fenêtre.",
    "target": "logistics_cost_per_unit",
    "targetLabel": "Coût logistique unitaire",
    "mode": "multiplicative",
    "allowedTargets": [
      {
        "id": "logistics_cost_per_unit",
        "label": "Coût logistique unitaire"
      },
      {
        "id": "unit_cost",
        "label": "Coût d'achat unitaire"
      }
    ],
    "defaultMagnitude": {
      "kind": "triangular",
      "low": 1.03,
      "mode": 1.08,
      "high": 1.15
    }
  },
  {
    "type": "demand_peak",
    "label": "Pic de demande",
    "description": "La demande augmente de 10 à 60 % pendant la fenêtre.",
    "target": "demand_mean_monthly",
    "targetLabel": "Demande moyenne mensuelle",
    "mode": "multiplicative",
    "allowedTargets": [
      {
        "id": "demand_mean_monthly",
        "label": "Demande moyenne mensuelle"
      }
    ],
    "defaultMagnitude": {
      "kind": "triangular",
      "low": 1.1,
      "mode": 1.3,
      "high": 1.6
    }
  },
  {
    "type": "key_customer_loss",
    "label": "Perte d'un client majeur",
    "description": "La demande baisse de 10 à 40 % pendant la fenêtre.",
    "target": "demand_mean_monthly",
    "targetLabel": "Demande moyenne mensuelle",
    "mode": "multiplicative",
    "allowedTargets": [
      {
        "id": "demand_mean_monthly",
        "label": "Demande moyenne mensuelle"
      }
    ],
    "defaultMagnitude": {
      "kind": "triangular",
      "low": 0.6,
      "mode": 0.75,
      "high": 0.9
    }
  },
];

export const EVENT_CATALOG_BY_TYPE: Record<EventType, EventCatalogEntry> = {
  "supplier_price_rise": EVENT_CATALOG[0],
  "supply_disruption": EVENT_CATALOG[1],
  "competitor_entry": EVENT_CATALOG[2],
  "power_outage": EVENT_CATALOG[3],
  "fx_shock": EVENT_CATALOG[4],
  "demand_peak": EVENT_CATALOG[5],
  "key_customer_loss": EVENT_CATALOG[6],
};
