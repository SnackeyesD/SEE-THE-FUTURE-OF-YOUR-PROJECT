"""Provenance d'un chiffre affiché dans le cockpit (phase 12).

Le service ne relance jamais de simulation : il réutilise le résultat conservé
par :class:`simulation_service.SimulationService`, dont la sensibilité a déjà
été calculée. Le payload produit par :func:`engine.build_provenance` ne contient
ni secret, ni chemin local, ni nom de projet.
"""

from __future__ import annotations

from typing import Any

from engine import build_provenance

from .simulation_service import SimulationService, SimulationServiceError


class ProvenanceServiceError(Exception):
    """Erreur métier traduite en erreur JSON-RPC par ``rpc.py``."""

    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


def _required_text(params: dict[str, Any], key: str) -> str:
    value = params.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ProvenanceServiceError(
            "provenance_invalid", f"{key} doit être une chaîne non vide"
        )
    return value.strip()


def _optional_point(params: dict[str, Any]) -> int | None:
    value = params.get("point")
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ProvenanceServiceError(
            "provenance_invalid", "point doit être un entier positif"
        )
    return value


def build(service: SimulationService, params: dict[str, Any]) -> dict[str, Any]:
    """Construit la provenance d'une métrique agrégée ou d'un point mensuel."""

    run_id = _required_text(params, "runId")
    metric = _required_text(params, "metric")
    point = _optional_point(params)

    try:
        job = service.job_for(run_id)
    except SimulationServiceError as exc:
        raise ProvenanceServiceError(
            exc.code, exc.message, retryable=exc.retryable
        ) from exc
    result = job.result
    if result is None:
        raise ProvenanceServiceError(
            "run_not_found",
            "ce run n'est plus disponible; relancez un calcul",
        )
    try:
        provenance = build_provenance(result, job.scenario, metric, point)
    except ValueError as exc:
        raise ProvenanceServiceError("provenance_invalid", str(exc)) from exc
    return {"provenance": provenance}


__all__ = ["ProvenanceServiceError", "build"]
