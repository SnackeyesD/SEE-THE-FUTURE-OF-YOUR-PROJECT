from __future__ import annotations

from typing import Any

import pytest

from agent_core import BriefContent


@pytest.fixture
def brief() -> dict[str, Any]:
    return BriefContent(
        problem="Les habitants du quartier manquent de boissons fraîches",
        customer="Ménages et petits commerces du quartier",
        value_proposition="Livraison rapide de boissons à prix accessible",
        revenue_model="Marge sur la vente au détail",
        cost_structure="Achat des stocks, loyer, logistique",
        geography="Abidjan, Côte d'Ivoire",
    ).model_dump(by_alias=True, exclude_none=True)


@pytest.fixture
def scenario_payload() -> dict[str, Any]:
    return {
        "name": "Dépôt de boissons",
        "currency": "XOF",
        "horizonMonths": 12,
        "assumptions": {
            "initial_cash": {"value": 2_000_000, "source": "estimation"},
            "unit_price": {
                "value": 500,
                "distribution": {"kind": "normal", "mean": 500, "std": 25},
                "source": "terrain",
            },
            "unit_cost": {
                "value": 320,
                "distribution": {"kind": "normal", "mean": 320, "std": 15},
                "source": "fournisseur",
            },
            "fixed_costs_monthly": {"value": 250_000, "source": "estimation"},
            "demand_mean_monthly": {
                "value": 2_300,
                "distribution": {"kind": "normal", "mean": 2_300, "std": 300},
                "source": "estimation",
            },
        },
    }
