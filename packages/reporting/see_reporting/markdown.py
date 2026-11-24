"""Constructeur Markdown déterministe.

Même ``ReportInput`` (date de génération incluse) donne exactement le même
texte. Aucune horloge, aucun aléatoire, aucun accès disque ou réseau : le
rapport est une fonction pure des faits persistés.
"""

from __future__ import annotations

from engine import DistributionSpec, ScenarioEvent

from .formatting import (
    format_date,
    format_money,
    format_number,
    format_optional,
    format_ratio,
)
from .models import ReportInput

DISCLAIMER = (
    "**Simulation basée sur vos hypothèses, pas une prévision garantie.** "
    "Les fourchettes décrivent la dispersion des tirages du moteur, pas une "
    "probabilité de réussite commerciale."
)

RELIABILITY_LABELS = {
    "official": "officielle",
    "study": "étude",
    "field": "terrain",
    "estimate": "estimation",
}

FRESHNESS_LABELS = {
    "fresh": "fraîche",
    "aging": "vieillissante",
    "stale": "périmée",
}

EVENT_LABELS = {
    "supplier_price_shock": "Choc prix fournisseur",
    "supply_disruption": "Rupture d'approvisionnement",
    "demand_drop": "Baisse de la demande",
    "demand_surge": "Pic de demande",
    "theft_or_loss": "Vol ou casse",
    "logistics_cost_increase": "Hausse logistique",
    "promotion": "Promotion",
    "competition_entry": "Arrivée d'un concurrent",
}


def build_markdown(report: ReportInput) -> str:
    result = report.result
    currency = result.currency or report.project.currency
    lines: list[str] = []
    _cover(lines, report, currency)
    _scope(lines)
    _assumptions(lines, report, currency)
    _results(lines, report, currency)
    _monthly(lines, report, currency)
    _sensitivity(lines, report)
    _events(lines, report)
    _branches(lines, report)
    _method(lines, report)
    _traceability(lines, report)
    if report.narration:
        _narration(lines, report.narration)
    return "\n".join(lines).rstrip() + "\n"


def _cover(lines: list[str], report: ReportInput, currency: str) -> None:
    project = report.project
    result = report.result
    lines.extend(
        [
            f"# Dossier de simulation — {project.name}",
            "",
            f"> {DISCLAIMER}",
            "",
            "| Élément | Valeur |",
            "|---|---|",
            f"| Projet | {project.name} |",
            f"| Devise | {currency} |",
            f"| Secteur | {project.sector or 'non renseigné'} |",
            f"| Scénario | {result.scenario_name} |",
            f"| Horizon | {result.horizon_months} mois |",
            f"| Graine | {result.seed} |",
            f"| Version du moteur | {result.engine_version} |",
            f"| Runs | {result.runs} |",
            f"| Qualité | {result.quality or 'non précisée'} |",
            f"| Date du dossier | {format_date(report.generated_at)} |",
            "",
        ]
    )


def _scope(lines: list[str]) -> None:
    lines.extend(
        [
            "## Ce que ce dossier contient",
            "",
            "- des hypothèses et leur provenance, telles qu'enregistrées ;",
            "- des agrégats produits par le moteur, sans recalcul dans le rapport ;",
            "- les branches et versions nommées qui tracent les variantes ;",
            "- les limites déclarées du modèle.",
            "",
            "## Ce qu'il ne contient pas",
            "",
            "- aucune clé d'API, aucun chemin local, aucune donnée personnelle ;",
            "- aucune prévision garantie ni recommandation d'investissement ;",
            "- aucune narration imposée : l'explication reste facultative.",
            "",
        ]
    )


def _input_unit(key: str) -> str | None:
    """Unité déclarée par le moteur, jamais devinée par le rapport."""

    try:
        from engine.models.retail_depot import INPUTS
    except Exception:  # pragma: no cover - modèle alternatif éventuel
        return None
    spec = INPUTS.get(key)
    return spec.unit if spec is not None else None


def _format_with_unit(value: float, unit: str | None, currency: str) -> str:
    if unit is None or unit.startswith("FCFA"):
        return format_money(value, currency, decimals=2)
    if unit == "fraction":
        return format_ratio(value, 2)
    if unit == "sans unité":
        return format_number(value, 2)
    return f"{format_number(value, 2)} {unit}"


def _assumptions(lines: list[str], report: ReportInput, currency: str) -> None:
    scenario = report.scenario
    lines.extend(["## Hypothèses et sources", ""])
    if scenario is None or not scenario.assumptions:
        lines.extend(["Aucune hypothèse enregistrée pour ce scénario.", ""])
        return
    lines.extend(
        [
            "| Hypothèse | Valeur | Fourchette | Source | Fiabilité | Date |",
            "|---|---|---|---|---|---|",
        ]
    )
    for key in sorted(scenario.assumptions):
        hypothesis = scenario.assumptions[key]
        unit = _input_unit(key)
        value = _format_with_unit(hypothesis.value, unit, currency)
        bounds: list[str] = []
        if hypothesis.min is not None:
            bounds.append(
                f"min {_format_with_unit(hypothesis.min, unit, currency)}"
            )
        if hypothesis.max is not None:
            bounds.append(
                f"max {_format_with_unit(hypothesis.max, unit, currency)}"
            )
        provenance = hypothesis.provenance
        source = hypothesis.source or "non renseignée"
        reliability = "non renseignée"
        source_date = "non disponible"
        if provenance is not None:
            source = provenance.label or source
            if provenance.reliability:
                reliability = RELIABILITY_LABELS.get(
                    provenance.reliability, provenance.reliability
                )
            source_date = format_date(provenance.source_date)
            if provenance.freshness:
                freshness = FRESHNESS_LABELS.get(
                    provenance.freshness, provenance.freshness
                )
                reliability += f" ({freshness})"
            if provenance.pack_id:
                source += f" — pack {provenance.pack_id}"
        lines.append(
            "| "
            + " | ".join(
                [
                    key,
                    value,
                    ", ".join(bounds) or "ponctuelle",
                    _escape(source),
                    reliability,
                    source_date,
                ]
            )
            + " |"
        )
    lines.append("")
    if scenario.notes:
        lines.extend([f"Notes du scénario : {scenario.notes}", ""])
    missing_sources = sorted(
        key
        for key, hypothesis in scenario.assumptions.items()
        if hypothesis.provenance is None and not hypothesis.source
    )
    if missing_sources:
        lines.extend(
            [
                "Hypothèses sans source déclarée : "
                + ", ".join(missing_sources)
                + ". Elles doivent être remplacées par des données réelles avant "
                "toute décision.",
                "",
            ]
        )


def _results(lines: list[str], report: ReportInput, currency: str) -> None:
    metrics = report.result.metrics
    break_even = report.result.break_even
    rows = [
        ("Profit cumulé P10", format_money(metrics.p10, currency)),
        ("Profit cumulé P50", format_money(metrics.p50, currency)),
        ("Profit cumulé P90", format_money(metrics.p90, currency)),
        ("Profit moyen", format_money(metrics.mean_profit, currency)),
        ("Probabilité de perte", format_ratio(metrics.loss_probability)),
        (
            "Probabilité de profit positif",
            format_ratio(metrics.profit_positive_probability),
        ),
        ("Chiffre d'affaires moyen", format_money(metrics.mean_revenue, currency)),
        ("Coûts moyens", format_money(metrics.mean_costs, currency)),
        ("Marge nette moyenne", format_ratio(metrics.mean_profit_margin)),
        ("Trésorerie minimale P50", _optional_money(metrics.min_cash_p50, currency)),
        ("Trésorerie minimale P10", _optional_money(metrics.min_cash_p10, currency)),
        ("Besoin de financement P50", _optional_money(metrics.financing_need_p50, currency)),
        ("Besoin de financement P90", _optional_money(metrics.financing_need_p90, currency)),
        (
            "Probabilité d'atteindre le point mort",
            format_optional(metrics.break_even_probability, format_ratio),
        ),
        (
            "Mois médian du point mort",
            format_optional(metrics.median_break_even_month, lambda v: f"mois {v}"),
        ),
    ]
    break_even_rows = [
        (
            "Charges fixes mensuelles",
            format_money(break_even.monthly_fixed_costs, currency),
        ),
        ("Marge unitaire", format_money(break_even.unit_margin, currency)),
        (
            "Unités mensuelles au point mort",
            format_optional(break_even.break_even_units_monthly, lambda v: format_number(v, 1)),
        ),
        (
            "Chiffre d'affaires mensuel au point mort",
            _optional_money(break_even.break_even_revenue_monthly, currency),
        ),
    ]
    lines.extend(["## Résultats du calcul final", "", "| Indicateur | Valeur |", "|---|---|"])
    lines.extend(f"| {label} | {value} |" for label, value in rows)
    lines.extend(["", "### Point mort structurel", "", "| Élément | Valeur |", "|---|---|"])
    lines.extend(f"| {label} | {value} |" for label, value in break_even_rows)
    lines.append("")


def _monthly(lines: list[str], report: ReportInput, currency: str) -> None:
    values = report.result.monthly.values
    lines.extend(["## Trajectoire mensuelle", ""])
    if not values:
        lines.extend(["Aucune trajectoire mensuelle disponible.", ""])
        return
    lines.extend(
        [
            "| Mois | Profit P10 | Profit P50 | Profit P90 | Trésorerie P50 "
            "| Probabilité point mort |",
            "|---|---|---|---|---|---|",
        ]
    )
    for point in values:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(point.month),
                    format_optional(point.profit_p10, lambda v: format_money(v, currency)),
                    format_optional(point.profit_p50, lambda v: format_money(v, currency)),
                    format_optional(point.profit_p90, lambda v: format_money(v, currency)),
                    format_optional(point.cash_p50, lambda v: format_money(v, currency)),
                    format_optional(point.break_even_probability, format_ratio),
                ]
            )
            + " |"
        )
    lines.append("")


def _sensitivity(lines: list[str], report: ReportInput) -> None:
    entries = sorted(
        report.result.sensitivity, key=lambda item: abs(item.contribution), reverse=True
    )
    lines.extend(["## Sensibilité", ""])
    if not entries:
        lines.extend(["Aucune sensibilité calculée pour ce run.", ""])
        return
    lines.extend(
        [
            "| Hypothèse | Corrélation | Contribution |",
            "|---|---|---|",
        ]
    )
    for entry in entries:
        lines.append(
            "| "
            + " | ".join(
                [
                    entry.hypothesis,
                    format_number(entry.correlation, 3),
                    format_number(entry.contribution, 3),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "Une contribution élevée indique une hypothèse qui déplace le résultat, "
            "pas une hypothèse certaine.",
            "",
        ]
    )


def _events(lines: list[str], report: ReportInput) -> None:
    scenario = report.scenario
    lines.extend(["## Événements", ""])
    events = scenario.events if scenario is not None else []
    if not events:
        lines.extend(["Aucun événement activé dans ce scénario.", ""])
        return
    lines.extend(
        [
            "| Événement | Type | Mois | Durée | Cible | Magnitude | Probabilité | Actif |",
            "|---|---|---|---|---|---|---|---|",
        ]
    )
    for event in sorted(events, key=lambda item: (item.start_month, item.id)):
        lines.append(
            "| "
            + " | ".join(
                [
                    event.id,
                    EVENT_LABELS.get(event.type, event.type),
                    str(event.start_month),
                    f"{event.duration_months} mois",
                    event.target,
                    _distribution(event),
                    format_ratio(event.probability),
                    "oui" if event.enabled else "non",
                ]
            )
            + " |"
        )
    lines.append("")


def _branches(lines: list[str], report: ReportInput) -> None:
    lines.extend(["## Branches et versions", ""])
    if not report.branches and not report.versions:
        lines.extend(["Aucune branche ni version nommée pour ce projet.", ""])
        return
    if report.branches:
        lines.extend(
            [
                "| Branche | Libellé | Parent | Dernier run final | Graine | Mise à jour |",
                "|---|---|---|---|---|---|",
            ]
        )
        for branch in report.branches:
            lines.append(
                "| "
                + " | ".join(
                    [
                        branch.name,
                        branch.branch_label or "—",
                        branch.parent_id or "racine",
                        branch.last_final_run_id or "aucun",
                        str(branch.seed) if branch.seed is not None else "non disponible",
                        format_date(branch.updated_at),
                    ]
                )
                + " |"
            )
        lines.append("")
    if report.versions:
        lines.extend(
            [
                "| Version | Scénario | Graine | Moteur | Créée le |",
                "|---|---|---|---|---|",
            ]
        )
        for version in report.versions:
            lines.append(
                "| "
                + " | ".join(
                    [
                        version.label,
                        version.scenario_id,
                        str(version.seed) if version.seed is not None else "non disponible",
                        version.engine_version or "non disponible",
                        format_date(version.created_at),
                    ]
                )
                + " |"
            )
        lines.append("")


def _method(lines: list[str], report: ReportInput) -> None:
    result = report.result
    lines.extend(["## Méthodologie et limites", ""])
    lines.extend(
        [
            f"- Modèle : `{result.model}`, horizon {result.horizon_months} mois.",
            f"- {result.runs} runs Monte Carlo, graine {result.seed}.",
            "- Le rapport ne calcule rien : il formate les agrégats du moteur.",
        ]
    )
    convergence = result.convergence
    if convergence is not None:
        lines.append(
            "- Convergence observée : "
            + ("stable" if convergence.converged else "non stable")
            + f" ({convergence.stable_blocks} blocs stables, variation relative maximale "
            + format_ratio(convergence.max_relative_change)
            + ")."
        )
    approximations = result.approximations or []
    if approximations:
        lines.append("- Approximations déclarées :")
        lines.extend(f"  - {item}" for item in approximations)
    lines.append("")


def _traceability(lines: list[str], report: ReportInput) -> None:
    result = report.result
    runs_retained = (
        result.runs_retained if result.runs_retained is not None else "non disponible"
    )
    lines.extend(
        [
            "## Traçabilité",
            "",
            "| Élément | Valeur |",
            "|---|---|",
            f"| Run | `{result.run_id}` |",
            f"| Graine | {result.seed} |",
            f"| Version du moteur | {result.engine_version} |",
            f"| Runs retenus | {runs_retained} |",
            f"| Schéma du rapport | {report.schema_version} |",
            "",
            "Pour reproduire ces chiffres : relancer le même scénario avec la même "
            "graine et la même version de moteur. Une comparaison entre deux runs "
            "n'est valable que si ces deux valeurs sont identiques.",
            "",
        ]
    )


def _narration(lines: list[str], narration: str) -> None:
    lines.extend(
        [
            "## Explication (facultative)",
            "",
            "> Texte généré par un fournisseur IA à partir des chiffres ci-dessus, "
            "puis vérifié numériquement. Il n'ajoute aucun chiffre.",
            "",
            narration.strip(),
            "",
        ]
    )


def _distribution(event: ScenarioEvent) -> str:
    return _describe(event.magnitude)


def _describe(spec: DistributionSpec) -> str:
    kind = spec.kind
    parts: list[str] = []
    for name in ("mean", "std", "sigma", "low", "mode", "high"):
        value = getattr(spec, name)
        if value is not None:
            parts.append(f"{name}={format_number(value, 2)}")
    if spec.values:
        parts.append(f"values={len(spec.values)}")
    if not parts:
        return kind
    return f"{kind} ({', '.join(parts)})"


def _optional_money(value: float | None, currency: str) -> str:
    return format_optional(value, lambda v: format_money(v, currency))


def _escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
