from __future__ import annotations

import numpy as np

from .scenario import SensitivityEntry


def build_sensitivity(
    samples: dict[str, np.ndarray],
    profit: np.ndarray,
) -> list[SensitivityEntry]:
    profit_std = float(profit.std(ddof=0))
    correlations: list[tuple[str, float]] = []

    for key in sorted(samples):
        values = samples[key]
        if profit_std == 0.0 or float(values.std(ddof=0)) == 0.0:
            correlation = 0.0
        else:
            correlation = float(np.corrcoef(values, profit)[0, 1])
            if not np.isfinite(correlation):
                correlation = 0.0
            correlation = float(np.clip(correlation, -1.0, 1.0))
        correlations.append((key, correlation))

    total = sum(correlation**2 for _, correlation in correlations)
    entries: list[SensitivityEntry] = []
    for key, correlation in correlations:
        contribution = correlation**2 / total if total > 0 else 0.0
        entries.append(
            SensitivityEntry(
                hypothesis=key,
                correlation=correlation,
                contribution=float(contribution),
            )
        )

    entries.sort(key=lambda entry: (-entry.contribution, entry.hypothesis))
    return entries
