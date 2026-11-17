"""Événements datés et chocs probabilistes du moteur.

Un événement modifie une cible mensuelle du modèle sur une fenêtre bornée, pour
une fraction des runs :

- ``start_month`` est **1-based** dans l'API, ``duration_months`` est inclusif ;
- l'occurrence et la magnitude sont tirées **une fois par run**, jamais par
  mois, et uniquement pour les runs actifs ;
- chaque événement possède ses propres slots de tirages
  (``event:<id>:active`` et ``event:<id>:magnitude``), donc ajouter, désactiver
  ou retirer un événement ne change jamais les tirages des hypothèses ni du
  bruit (ADR 0010, ADR 0015).

Le catalogue est une donnée : la phase 10 peut construire l'UI d'édition à
partir de :data:`EVENT_CATALOG` sans modifier le moteur.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
from pydantic import Field, model_validator

from .distributions import distribution_streams, sample_distribution
from .draws import DrawBank
from .schema import CamelModel, DistributionSpec

EventType = Literal[
    "supplier_price_rise",
    "supply_disruption",
    "competitor_entry",
    "power_outage",
    "fx_shock",
    "demand_peak",
    "key_customer_loss",
]

EventMode = Literal["multiplicative", "additive"]

EVENT_ID_PATTERN = r"^[a-z][a-z0-9_-]{0,63}$"


@dataclass(frozen=True)
class EventTarget:
    """Cible modifiable par un événement, avec son domaine de validité.

    Les bornes servent à ramener un effet **additif** dans le domaine du
    modèle : un taux de perte ne peut pas dépasser 1 et un délai de
    réapprovisionnement reste sous 24 mois. Un effet **multiplicatif** reste
    strictement positif par validation de sa magnitude.
    """

    key: str
    label: str
    minimum: float = 0.0
    maximum: float | None = None


EVENT_TARGETS: dict[str, EventTarget] = {
    target.key: target
    for target in (
        EventTarget("unit_cost", "Coût d'achat unitaire"),
        EventTarget("logistics_cost_per_unit", "Coût logistique unitaire"),
        EventTarget("fixed_costs_monthly", "Coûts fixes mensuels"),
        EventTarget("demand_mean_monthly", "Demande moyenne mensuelle"),
        EventTarget("loss_rate", "Taux de perte mensuel", maximum=1.0),
        EventTarget("reorder_lead_time_months", "Délai de réapprovisionnement", maximum=24.0),
    )
}


@dataclass(frozen=True)
class EventSpec:
    """Description d'un type d'événement du catalogue.

    ``target`` et ``mode`` sont les valeurs par défaut proposées par l'UI ;
    ``allowed_targets`` borne ce qu'un scénario peut demander. ``label`` et
    ``description`` sont destinés à l'affichage (phase 10) et ne participent
    pas au calcul.
    """

    target: str
    mode: EventMode
    default_magnitude: DistributionSpec
    allowed_targets: frozenset[str]
    label: str = ""
    description: str = ""


def _magnitude(
    kind: str = "triangular",
    **parameters: float,
) -> DistributionSpec:
    return DistributionSpec(kind=kind, **parameters)  # type: ignore[arg-type]


EVENT_CATALOG: dict[EventType, EventSpec] = {
    "supplier_price_rise": EventSpec(
        target="unit_cost",
        mode="multiplicative",
        default_magnitude=_magnitude(low=1.05, mode=1.15, high=1.30),
        allowed_targets=frozenset({"unit_cost", "logistics_cost_per_unit"}),
        label="Hausse du prix fournisseur",
        description="Le coût d'achat augmente de 5 à 30 % pendant la fenêtre.",
    ),
    "supply_disruption": EventSpec(
        target="reorder_lead_time_months",
        mode="additive",
        default_magnitude=_magnitude(low=1.0, mode=2.0, high=4.0),
        allowed_targets=frozenset({"reorder_lead_time_months", "loss_rate"}),
        label="Rupture d'approvisionnement",
        description="Le délai de livraison s'allonge de 1 à 4 mois (ou les pertes augmentent).",
    ),
    "competitor_entry": EventSpec(
        target="demand_mean_monthly",
        mode="multiplicative",
        default_magnitude=_magnitude(low=0.70, mode=0.85, high=0.95),
        allowed_targets=frozenset({"demand_mean_monthly"}),
        label="Arrivée d'un concurrent",
        description="La demande baisse de 5 à 30 % pendant la fenêtre.",
    ),
    "power_outage": EventSpec(
        target="loss_rate",
        mode="additive",
        default_magnitude=_magnitude("uniform", low=0.01, high=0.05),
        allowed_targets=frozenset({"loss_rate", "fixed_costs_monthly"}),
        label="Coupure d'électricité prolongée",
        description="Les pertes de stock augmentent de 1 à 5 points par mois.",
    ),
    "fx_shock": EventSpec(
        target="logistics_cost_per_unit",
        mode="multiplicative",
        default_magnitude=_magnitude(low=1.03, mode=1.08, high=1.15),
        allowed_targets=frozenset({"logistics_cost_per_unit", "unit_cost"}),
        label="Choc de change",
        description="La logistique augmente de 3 à 15 % pendant la fenêtre.",
    ),
    "demand_peak": EventSpec(
        target="demand_mean_monthly",
        mode="multiplicative",
        default_magnitude=_magnitude(low=1.10, mode=1.30, high=1.60),
        allowed_targets=frozenset({"demand_mean_monthly"}),
        label="Pic de demande",
        description="La demande augmente de 10 à 60 % pendant la fenêtre.",
    ),
    "key_customer_loss": EventSpec(
        target="demand_mean_monthly",
        mode="multiplicative",
        default_magnitude=_magnitude(low=0.60, mode=0.75, high=0.90),
        allowed_targets=frozenset({"demand_mean_monthly"}),
        label="Perte d'un client majeur",
        description="La demande baisse de 10 à 40 % pendant la fenêtre.",
    ),
}


def magnitude_is_strictly_positive(spec: DistributionSpec) -> bool:
    """Indique si une magnitude ne peut jamais produire une valeur ≤ 0.

    Une loi normale ou de Poisson peut atteindre zéro (voire devenir négative
    pour la normale) : elle est refusée pour un effet multiplicatif, qui
    rendrait un coût ou une demande négatifs.
    """

    if spec.kind == "lognormal":
        return True
    if spec.kind in ("uniform", "triangular"):
        return spec.low is not None and spec.low > 0
    if spec.kind == "empirical":
        return bool(spec.values) and min(spec.values) > 0
    return False


class ScenarioEvent(CamelModel):
    id: str = Field(pattern=EVENT_ID_PATTERN, max_length=64)
    type: EventType
    start_month: int = Field(ge=1, le=120)
    duration_months: int = Field(ge=1, le=120)
    target: str = Field(min_length=1, max_length=64)
    mode: EventMode = "multiplicative"
    magnitude: DistributionSpec
    probability: float = Field(default=1.0, ge=0.0, le=1.0)
    enabled: bool = True

    @model_validator(mode="after")
    def _check_catalog(self) -> ScenarioEvent:
        spec = EVENT_CATALOG[self.type]
        if self.target not in spec.allowed_targets:
            allowed = ", ".join(sorted(spec.allowed_targets))
            raise ValueError(
                f"événement {self.id!r}: cible {self.target!r} non autorisée pour "
                f"{self.type}; cibles possibles: {allowed}"
            )
        if self.mode == "multiplicative" and not magnitude_is_strictly_positive(self.magnitude):
            raise ValueError(
                f"événement {self.id!r}: une magnitude multiplicative doit être "
                "strictement positive; utilisez une lognormale, une uniforme ou une "
                "triangulaire à borne basse positive, ou une empirique positive"
            )
        return self


def event_slots(event: ScenarioEvent) -> tuple[str, str]:
    """Noms des slots d'occurrence et de magnitude d'un événement."""

    return (f"event:{event.id}:active", f"event:{event.id}:magnitude")


def register_event_slots(bank: DrawBank, events: Iterable[ScenarioEvent]) -> None:
    """Enregistre les slots des événements **actifs**, triés par identifiant.

    Les événements désactivés ne consomment aucun tirage et n'apparaissent donc
    pas dans la banque.
    """

    for event in sorted(
        (candidate for candidate in events if candidate.enabled),
        key=lambda candidate: candidate.id,
    ):
        active_slot, magnitude_slot = event_slots(event)
        bank.register(active_slot)
        bank.register(magnitude_slot)


@dataclass(frozen=True)
class EventDraws:
    """Tirages d'événements pour l'ensemble des runs.

    L'occurrence et la magnitude sont tirées une fois pour tous les runs, avant
    la boucle de blocs : deux scalaires par run et par événement, soit beaucoup
    moins que le bruit. Les modificateurs restent, eux, construits bloc par
    bloc pour borner la mémoire.

    ``events`` conserve les événements actifs triés par identifiant : les
    modificateurs sont ainsi construits dans un ordre stable sans re-trier à
    chaque bloc, et l'ensemble des événements ne peut pas diverger des tirages.
    """

    events: tuple[ScenarioEvent, ...]
    active: Mapping[str, np.ndarray]
    magnitude: Mapping[str, np.ndarray]


def draw_events(
    events: Iterable[ScenarioEvent],
    bank: DrawBank,
    runs: int,
) -> EventDraws | None:
    """Tire l'occurrence et la magnitude de chaque événement actif.

    ``None`` signifie « aucun événement actif » : le modèle suivra le chemin
    rapide et aucune table de modificateurs ne sera construite.
    """

    enabled = sorted(
        (event for event in events if event.enabled),
        key=lambda event: event.id,
    )
    if not enabled:
        return None
    if runs < 0:
        raise ValueError("runs doit être positif ou nul")

    active_flags: dict[str, np.ndarray] = {}
    magnitudes: dict[str, np.ndarray] = {}
    for event in enabled:
        active_slot, magnitude_slot = event_slots(event)
        bank.register(active_slot)
        bank.register(magnitude_slot)

        uniform, _ = bank.take(
            active_slot,
            runs,
            uniform=True,
            normal=False,
        )
        assert uniform is not None
        # Un tirage strictement inférieur à p : p=1 est toujours actif,
        # p=0 ne l'est jamais, et l'occurrence ne dépend pas du mois.
        active_flags[event.id] = uniform < event.probability

        needs_uniform, needs_normal = distribution_streams(event.magnitude)
        magnitudes_uniform, magnitudes_normal = bank.take(
            magnitude_slot,
            runs,
            uniform=needs_uniform,
            normal=needs_normal,
        )
        magnitudes[event.id] = sample_distribution(
            event.magnitude,
            magnitudes_uniform,
            magnitudes_normal,
        )

    return EventDraws(events=tuple(enabled), active=active_flags, magnitude=magnitudes)


@dataclass(frozen=True)
class EventModifiers:
    """Modificateurs mensuels par cible : ``valeur × facteur + décalage``.

    Les tableaux ont la forme ``(runs du lot, horizon)``. ``factors`` contient
    les effets multiplicatifs (initialisés à ``1.0``) et ``offsets`` les effets
    additifs (initialisés à ``0.0``). Décomposer les deux évite qu'un événement
    additif et un événement multiplicatif sur la même cible ne s'écrasent.
    """

    factors: Mapping[str, np.ndarray] = field(default_factory=dict)
    offsets: Mapping[str, np.ndarray] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return bool(self.factors) or bool(self.offsets)

    @property
    def targets(self) -> frozenset[str]:
        return frozenset(self.factors) | frozenset(self.offsets)


def build_event_modifiers(
    draws: EventDraws | None,
    start: int,
    end: int,
    horizon: int,
) -> EventModifiers | None:
    """Construit les modificateurs du lot ``[start, end)``, ou ``None``.

    ``None`` signale au modèle qu'il peut suivre le chemin rapide sans
    événement. Seules les cibles réellement touchées sont matérialisées.
    """

    if draws is None or not draws.events:
        return None
    if start < 0 or end <= start or horizon < 1:
        raise ValueError("fenêtre de modificateurs invalide")
    if end > len(next(iter(draws.active.values()))):
        raise ValueError("tirages d'événements trop courts pour la fenêtre demandée")

    count = end - start
    factors: dict[str, np.ndarray] = {}
    offsets: dict[str, np.ndarray] = {}

    for event in draws.events:
        active = draws.active[event.id][start:end]
        if not active.any():
            continue
        magnitudes = draws.magnitude[event.id][start:end]

        table = factors if event.mode == "multiplicative" else offsets
        array = table.get(event.target)
        if array is None:
            fill = np.ones if event.mode == "multiplicative" else np.zeros
            array = fill((count, horizon), dtype=np.float64)
            table[event.target] = array

        start_month = event.start_month - 1
        window = slice(start_month, start_month + event.duration_months)
        # La tranche de mois est une vue : l'affectation par lignes actives
        # écrit directement dans la table, sans copie intermédiaire du lot.
        block = array[:, window]
        if event.mode == "multiplicative":
            block[active] *= magnitudes[active][:, None]
        else:
            block[active] += magnitudes[active][:, None]

    for target, array in offsets.items():
        bounds = EVENT_TARGETS[target]
        upper = np.inf if bounds.maximum is None else bounds.maximum
        np.clip(array, bounds.minimum, upper, out=array)

    return EventModifiers(factors=factors, offsets=offsets)
