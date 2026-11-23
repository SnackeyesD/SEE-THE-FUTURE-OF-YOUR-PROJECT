"""Provenance d'un chiffre et validation numérique des explications.

Ce module construit un payload minimal à partir d'un résultat moteur, sans
relancer de simulation. Il fournit aussi le repli déterministe et le
validateur utilisé par le sidecar avant d'afficher une explication LLM.

Règles :

- aucun secret, chemin local ou nom de projet n'entre dans le payload ;
- la sensibilité réutilise ``result.sensitivity`` (corrélation et
  contribution déjà calculées) ;
- un nombre présent dans une explication doit exister dans le payload, aux
  libellés ``P10``/``P50``/``P90`` près ;
- la tolérance d'arrondi est relative (0,1 %) et documentée.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from typing import Any

from .scenario import Scenario, SimulationResult

ROUNDING_TOLERANCE = 0.001
"""Tolérance relative acceptée pour un nombre arrondi (0,1 %)."""


def scenario_hash(scenario: Scenario) -> str:
    """Hash canonique du scénario, hors nom et notes volatiles."""

    payload = scenario.model_dump(by_alias=True, exclude_none=True)
    payload.pop("name", None)
    payload.pop("notes", None)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


_AGGREGATE_METRICS: dict[str, tuple[str, str, str, str]] = {
    "profit_p50": (
        "metrics.p50",
        "Profit cumulé médian (P50) sur l'horizon.",
        "Quantile P50 des profits cumulés des runs.",
        "currency",
    ),
    "profit_p10": (
        "metrics.p10",
        "Profit cumulé pessimiste (P10) sur l'horizon.",
        "Quantile P10 des profits cumulés des runs.",
        "currency",
    ),
    "profit_p90": (
        "metrics.p90",
        "Profit cumulé favorable (P90) sur l'horizon.",
        "Quantile P90 des profits cumulés des runs.",
        "currency",
    ),
    "mean_profit": (
        "metrics.mean_profit",
        "Profit cumulé moyen sur l'horizon.",
        "Moyenne des profits cumulés des runs.",
        "currency",
    ),
    "loss_probability": (
        "metrics.loss_probability",
        "Probabilité que le profit cumulé soit négatif.",
        "Part des runs dont le profit cumulé est strictement négatif.",
        "probability",
    ),
    "profit_positive_probability": (
        "metrics.profit_positive_probability",
        "Probabilité que le profit cumulé soit positif.",
        "Part des runs dont le profit cumulé est positif.",
        "probability",
    ),
    "cash_negative_probability": (
        "metrics.cash_negative_probability",
        "Probabilité que la trésorerie minimale devienne négative.",
        "Part des runs dont la trésorerie mensuelle passe sous zéro.",
        "probability",
    ),
    "min_cash_p10": (
        "metrics.min_cash_p10",
        "Trésorerie minimale pessimiste (P10).",
        "Quantile P10 des trésoreries minimales des runs.",
        "currency",
    ),
    "min_cash_p50": (
        "metrics.min_cash_p50",
        "Trésorerie minimale médiane (P50).",
        "Quantile P50 des trésoreries minimales des runs.",
        "currency",
    ),
    "min_cash_p90": (
        "metrics.min_cash_p90",
        "Trésorerie minimale favorable (P90).",
        "Quantile P90 des trésoreries minimales des runs.",
        "currency",
    ),
    "financing_need_p50": (
        "metrics.financing_need_p50",
        "Besoin de financement médian (P50).",
        "Opposé de la trésorerie minimale P50 lorsqu'elle est négative, sinon zéro.",
        "currency",
    ),
    "financing_need_p90": (
        "metrics.financing_need_p90",
        "Besoin de financement pessimiste (P90).",
        "Opposé de la trésorerie minimale P90 lorsqu'elle est négative, sinon zéro.",
        "currency",
    ),
    "break_even_probability": (
        "metrics.break_even_probability",
        "Probabilité d'atteindre le point mort sur l'horizon.",
        "Part des runs dont le profit cumulé devient positif avant la fin de l'horizon.",
        "probability",
    ),
    "break_even_months_p50": (
        "metrics.median_break_even_month",
        "Mois médian d'atteinte du point mort.",
        "Quantile P50 du mois où le profit cumulé devient positif.",
        "months",
    ),
}

_POINT_METRICS: dict[str, tuple[str, str, str, str]] = {
    "profit_p50": (
        "profit_p50",
        "Profit mensuel médian (P50) pour le mois demandé.",
        "Quantile P50 des profits du mois sur les runs.",
        "currency",
    ),
    "profit_p10": (
        "profit_p10",
        "Profit mensuel pessimiste (P10) pour le mois demandé.",
        "Quantile P10 des profits du mois sur les runs.",
        "currency",
    ),
    "profit_p90": (
        "profit_p90",
        "Profit mensuel favorable (P90) pour le mois demandé.",
        "Quantile P90 des profits du mois sur les runs.",
        "currency",
    ),
    "profit_mean": (
        "mean_profit",
        "Profit mensuel moyen pour le mois demandé.",
        "Moyenne des profits du mois sur les runs.",
        "currency",
    ),
    "cash_p50": (
        "cash_p50",
        "Trésorerie mensuelle médiane (P50) pour le mois demandé.",
        "Quantile P50 de la trésorerie du mois sur les runs.",
        "currency",
    ),
    "cash_p10": (
        "cash_p10",
        "Trésorerie mensuelle pessimiste (P10) pour le mois demandé.",
        "Quantile P10 de la trésorerie du mois sur les runs.",
        "currency",
    ),
    "cash_p90": (
        "cash_p90",
        "Trésorerie mensuelle favorable (P90) pour le mois demandé.",
        "Quantile P90 de la trésorerie du mois sur les runs.",
        "currency",
    ),
    "revenue_mean": (
        "mean_revenue",
        "Revenu mensuel moyen pour le mois demandé.",
        "Moyenne des revenus du mois sur les runs.",
        "currency",
    ),
    "demand_mean": (
        "mean_demand",
        "Demande mensuelle moyenne pour le mois demandé.",
        "Moyenne de la demande du mois sur les runs.",
        "units",
    ),
    "break_even_probability": (
        "break_even_probability",
        "Probabilité d'atteindre le point mort au plus tard au mois demandé.",
        "Part des runs dont le point mort est atteint avant ou pendant le mois.",
        "probability",
    ),
}


def _nested(result: SimulationResult, path: str) -> Any:
    value: Any = result
    for part in path.split("."):
        value = getattr(value, part)
    return value


def _metric_label(metric: str) -> str:
    return metric.replace("_", " ")


def _resolve_metric(
    result: SimulationResult, metric: str, point: int | None
) -> tuple[float, str, str, str, list[float] | None]:
    if point is None:
        if metric not in _AGGREGATE_METRICS:
            raise ValueError(f"métrique de provenance inconnue: {metric}")
        path, definition, formula, unit_kind = _AGGREGATE_METRICS[metric]
        raw = _nested(result, path)
        if raw is None:
            raise ValueError(f"métrique indisponible dans ce résultat: {metric}")
        value = float(raw)
        range_values = None
        if metric in {"profit_p50", "profit_p10", "profit_p90"}:
            range_values = [result.metrics.p10, result.metrics.p90]
        elif metric in {"min_cash_p50", "min_cash_p10", "min_cash_p90"}:
            if result.metrics.min_cash_p10 is not None and result.metrics.min_cash_p90 is not None:
                range_values = [result.metrics.min_cash_p10, result.metrics.min_cash_p90]
        elif metric in {"financing_need_p50", "financing_need_p90"}:
            if (
                result.metrics.financing_need_p50 is not None
                and result.metrics.financing_need_p90 is not None
            ):
                range_values = [
                    result.metrics.financing_need_p50,
                    result.metrics.financing_need_p90,
                ]
        return value, definition, formula, unit_kind, range_values

    if point < 1 or point > result.horizon_months:
        raise ValueError(f"mois hors horizon: {point}")
    entry = next(
        (item for item in result.monthly.values if item.index == point),
        None,
    )
    if entry is None:
        raise ValueError(f"aucune valeur mensuelle pour le mois {point}")
    if metric not in _POINT_METRICS:
        raise ValueError(f"métrique mensuelle de provenance inconnue: {metric}")
    attribute, definition, formula, unit_kind = _POINT_METRICS[metric]
    raw = getattr(entry, attribute)
    if raw is None:
        raise ValueError(f"métrique mensuelle indisponible: {metric} au mois {point}")
    value = float(raw)
    range_values = None
    if metric == "profit_p50" and entry.profit_p10 is not None and entry.profit_p90 is not None:
        range_values = [entry.profit_p10, entry.profit_p90]
    elif metric == "cash_p50" and entry.cash_p10 is not None and entry.cash_p90 is not None:
        range_values = [entry.cash_p10, entry.cash_p90]
    return value, definition, formula, unit_kind, range_values


def _unit_label(unit_kind: str, currency: str) -> str:
    if unit_kind == "currency":
        return currency
    if unit_kind == "probability":
        return "%"
    if unit_kind == "months":
        return "mois"
    if unit_kind == "units":
        return "unités"
    return ""


def _input_source(hypothesis: Any) -> str:
    provenance = getattr(hypothesis, "provenance", None)
    if provenance is not None and getattr(provenance, "kind", None) == "benchmark":
        return "benchmark"
    source = (getattr(hypothesis, "source", None) or "").strip().lower()
    if "bench" in source:
        return "benchmark"
    if source and source not in {"user", "utilisateur", "manual", "manuel"}:
        return "estimate"
    return "user"


def _benchmark_payload(hypothesis: Any) -> dict[str, Any] | None:
    provenance = getattr(hypothesis, "provenance", None)
    if provenance is None or getattr(provenance, "kind", None) != "benchmark":
        return None
    return {
        "label": provenance.label,
        "source": provenance.source,
        "url": provenance.source_url,
        "date": provenance.source_date,
    }


def _input_label(key: str) -> str:
    try:
        from .models.retail_depot import INPUTS
    except Exception:  # pragma: no cover - modèle alternatif éventuel
        return key
    spec = INPUTS.get(key)
    return spec.label if spec is not None else key


def build_provenance(
    result: SimulationResult,
    scenario: Scenario,
    metric: str,
    point: int | None = None,
) -> dict[str, Any]:
    """Construit le payload de provenance d'une métrique agrégée ou mensuelle."""

    value, definition, formula, unit_kind, range_values = _resolve_metric(
        result, metric, point
    )
    sensitivity = {
        entry.hypothesis: entry for entry in result.sensitivity
    }
    inputs: list[dict[str, Any]] = []
    for key in sorted(scenario.assumptions):
        hypothesis = scenario.assumptions[key]
        entry = sensitivity.get(key)
        drawn_min = hypothesis.min
        drawn_max = hypothesis.max
        if drawn_min is None or drawn_max is None:
            try:
                from .models import get_model

                model_min, model_max = get_model(scenario.model).bounds(key)
            except Exception:  # pragma: no cover - modèle inconnu
                model_min, model_max = None, None
            drawn_min = drawn_min if drawn_min is not None else model_min
            drawn_max = drawn_max if drawn_max is not None else model_max
        if drawn_min is None:
            drawn_min = hypothesis.value
        if drawn_max is None:
            drawn_max = max(hypothesis.value, drawn_min)
        inputs.append(
            {
                "key": key,
                "label": _input_label(key),
                "value": hypothesis.value,
                "drawnRange": [float(drawn_min), float(drawn_max)],
                "source": _input_source(hypothesis),
                "confidence": hypothesis.confidence,
                "benchmark": _benchmark_payload(hypothesis),
                "correlation": float(entry.correlation) if entry is not None else 0.0,
                "contribution": float(entry.contribution) if entry is not None else 0.0,
            }
        )

    caveats = [
        "La sensibilité est une corrélation, pas une relation causale.",
        "Les valeurs sont conditionnelles aux hypothèses du scénario et à la graine.",
        "La provenance décrit ce calcul ; elle ne constitue pas une prévision.",
    ]
    if result.quality == "draft":
        caveats.append("Ce résultat est un brouillon et ne doit pas servir de référence finale.")
    if result.approximations:
        caveats.append(
            "Approximations de distribution utilisées : "
            + ", ".join(result.approximations)
            + "."
        )

    return {
        "runId": result.run_id,
        "metric": metric,
        "point": point,
        "definition": definition,
        "formula": formula,
        "value": value,
        "unit": _unit_label(unit_kind, result.currency),
        "range": range_values,
        "seed": result.seed,
        "engineVersion": result.engine_version,
        "runs": result.runs,
        "scenariosHash": scenario_hash(scenario),
        "inputs": inputs,
        "caveats": caveats,
    }


def _iter_numbers(value: Any) -> Iterable[float]:
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        if value == value:  # exclut NaN
            yield float(value)
        return
    if isinstance(value, Mapping):
        for item in value.values():
            yield from _iter_numbers(item)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            yield from _iter_numbers(item)


_NUMBER_RE = re.compile(r"[-+]?(?:\d+(?:[.,]\d+)?)")
_PERCENT_SUFFIX = re.compile(r"^\s*%")
_P_LABEL_RE = re.compile(r"\b[Pp]\s*(?:10|50|90)\b")


def _clean_thousands(text: str) -> str:
    cleaned = text
    # Espaces fines/insécables et espaces ordinaires utilisés comme séparateurs
    # de milliers. On répète pour les nombres à plusieurs groupes.
    pattern = re.compile(r"(?<=\d)[\u00a0\u202f\u2009 ](?=\d{3}(?!\d))")
    previous = None
    while previous != cleaned:
        previous = cleaned
        cleaned = pattern.sub("", cleaned)
    return cleaned.replace("\u2019", "").replace("'", "")


def extract_numbers(text: str) -> list[tuple[float, bool]]:
    """Extrait les nombres d'un texte français.

    Retourne ``(valeur, est_pourcentage)``. Les libellés ``P10``, ``P50`` et
    ``P90`` sont retirés avant l'extraction : ce sont des noms de quantiles,
    pas des nombres inventés.
    """

    if not isinstance(text, str):
        return []
    cleaned = _P_LABEL_RE.sub(" ", text)
    cleaned = _clean_thousands(cleaned)
    numbers: list[tuple[float, bool]] = []
    for match in _NUMBER_RE.finditer(cleaned):
        raw = match.group(0)
        if not raw or raw in {"-", "+"}:
            continue
        normalized = raw.replace(",", ".")
        try:
            value = float(normalized)
        except ValueError:
            continue
        following = cleaned[match.end() : match.end() + 2]
        numbers.append((value, bool(_PERCENT_SUFFIX.match(following))))
    return numbers


def allowed_numbers(provenance: Mapping[str, Any]) -> set[float]:
    """Ensemble des nombres présents dans le payload (hors runId et hash)."""

    allowed: set[float] = set()
    for key in ("value", "seed", "runs", "point", "range"):
        allowed.update(_iter_numbers(provenance.get(key)))
    for item in provenance.get("inputs", []):
        allowed.update(_iter_numbers(item))
    for key in ("definition", "formula", "unit", "engineVersion"):
        allowed.update(value for value, _ in extract_numbers(str(provenance.get(key, ""))))
    for caveat in provenance.get("caveats", []):
        allowed.update(value for value, _ in extract_numbers(str(caveat)))
    return allowed


def number_is_allowed(
    value: float,
    *,
    is_percent: bool,
    allowed: set[float],
    tolerance: float = ROUNDING_TOLERANCE,
) -> bool:
    candidates = [value]
    if is_percent:
        candidates.append(value / 100.0)
    for candidate in candidates:
        for expected in allowed:
            difference = abs(candidate - expected)
            if difference <= max(abs(expected) * tolerance, 1e-9):
                return True
    return False


def validate_explanation(
    explanation: Mapping[str, Any],
    provenance: Mapping[str, Any],
) -> list[str]:
    """Retourne les nombres inconnus d'une explication (vide si valide)."""

    allowed = allowed_numbers(provenance)
    texts: list[str] = [str(explanation.get("summary", ""))]
    for point in explanation.get("points", []):
        texts.append(str(point.get("text", "")))
    for caveat in explanation.get("caveats", []):
        texts.append(str(caveat))
    unknown: list[str] = []
    for text in texts:
        for value, is_percent in extract_numbers(text):
            if not number_is_allowed(value, is_percent=is_percent, allowed=allowed):
                rendered = _render_unknown(value, is_percent=is_percent)
                if rendered not in unknown:
                    unknown.append(rendered)
    return unknown


def _render_unknown(value: float, *, is_percent: bool) -> str:
    """Rend un nombre inconnu au format français, pour le message d'erreur."""

    rendered = f"{value:,.6f}".rstrip("0").rstrip(".")
    rendered = rendered.replace(",", " ").replace(".", ",")
    if is_percent:
        rendered += " %"
    return rendered


def _format_number(value: float, unit: str) -> str:
    if unit == "%":
        return f"{value * 100:.1f} %".replace(".", ",")
    if unit == "mois":
        return f"{value:.1f} mois".replace(".", ",")
    if unit == "unités":
        return f"{value:,.0f} unités".replace(",", " ")
    rendered = f"{value:,.0f}".replace(",", " ")
    return f"{rendered} {unit}".strip()


def deterministic_explanation(provenance: Mapping[str, Any]) -> dict[str, Any]:
    """Repli sans fournisseur, construit uniquement à partir du payload."""

    unit = str(provenance.get("unit", ""))
    value = float(provenance.get("value", 0.0))
    seed = provenance.get("seed")
    runs = provenance.get("runs")
    point = provenance.get("point")
    range_values = provenance.get("range")
    horizon = f" au mois {point}" if point is not None else ""
    summary = (
        f"{provenance.get('definition', '')} La valeur retenue{horizon} est "
        f"{_format_number(value, unit)}. Elle provient de {runs} runs reproductibles "
        f"avec la graine {seed}."
    )
    points: list[dict[str, Any]] = [
        {
            "text": (
                f"Formule : {provenance.get('formula', '')} "
                f"Le moteur {provenance.get('engineVersion', '')} a produit cette valeur."
            ),
            "references": ["formula", "engineVersion"],
        }
    ]
    if isinstance(range_values, list) and len(range_values) == 2:
        points.append(
            {
                "text": (
                    "La fourchette P10–P90 est "
                    f"{_format_number(float(range_values[0]), unit)} – "
                    f"{_format_number(float(range_values[1]), unit)}."
                ),
                "references": ["p10", "p90"],
            }
        )
    inputs = provenance.get("inputs") or []
    if inputs:
        top = max(inputs, key=lambda item: abs(float(item.get("contribution", 0.0))))
        points.append(
            {
                "text": (
                    f"L'hypothèse la plus contributive est {top.get('label')} "
                    f"({_format_number(float(top.get('contribution', 0.0)), '%')} "
                    "de la variance observée). C'est une corrélation, pas une causalité."
                ),
                "references": [str(top.get("key", ""))],
            }
        )
    return {
        "summary": summary,
        "points": points,
        "caveats": list(provenance.get("caveats") or []),
    }
