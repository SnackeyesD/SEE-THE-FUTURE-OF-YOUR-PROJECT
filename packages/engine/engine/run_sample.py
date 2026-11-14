from __future__ import annotations

from dataclasses import dataclass

import numpy as np

SAMPLE_LIMIT = 20_000
"""Nombre maximal de runs conservés pour les bandes et trajectoires.

L'échantillon est toujours un **préfixe** des runs : augmenter le nombre de
runs ne change pas les runs déjà conservés.
"""


@dataclass(frozen=True, eq=False)
class RunSample:
    """Échantillon interne de runs, jamais sérialisé avec le résultat.

    Les tableaux sont contigus et en ``float64``. Ils servent aux bandes
    mensuelles, aux histogrammes mensuels et, plus tard, aux trajectoires.
    """

    indices: np.ndarray
    profit_monthly: np.ndarray
    cash_monthly: np.ndarray
    revenue_monthly: np.ndarray
    parameters: dict[str, np.ndarray]
