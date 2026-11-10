from __future__ import annotations


class EngineError(Exception):
    """Erreur métier du moteur, distincte d'une erreur de programmation."""


class UnknownModelError(EngineError):
    def __init__(self, model: str) -> None:
        super().__init__(f"modèle de simulation inconnu: {model}")
        self.model = model
