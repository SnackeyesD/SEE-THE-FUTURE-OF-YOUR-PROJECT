from __future__ import annotations


class EngineError(Exception):
    """Erreur métier du moteur, distincte d'une erreur de programmation."""


class UnknownModelError(EngineError):
    def __init__(self, model: str) -> None:
        super().__init__(f"modèle de simulation inconnu: {model}")
        self.model = model


class SimulationCancelled(EngineError):
    """Calcul interrompu par l'utilisateur ou remplacé par un nouveau run.

    Le moteur s'arrête entre deux blocs : le bloc en cours est terminé puis
    abandonné, aucun agrégat partiel supplémentaire n'est publié.
    """

    def __init__(self, completed_runs: int = 0, total_runs: int = 0) -> None:
        if total_runs:
            message = (
                f"simulation annulée après {completed_runs} run(s) "
                f"sur {total_runs}"
            )
        else:
            message = f"simulation annulée après {completed_runs} run(s)"
        super().__init__(message)
        self.completed_runs = completed_runs
        self.total_runs = total_runs
