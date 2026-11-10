import numpy as np
import pandas as pd


def main(data):
    rows = int(data.get("rows", 12)) if isinstance(data, dict) else 12
    frame = pd.DataFrame(
        {
            "mois": np.arange(1, rows + 1),
            "revenu": np.linspace(1_000, 2_000, rows),
        }
    )
    return {
        "summary": "Projection linéaire calculée dans la sandbox.",
        "metrics": [
            {"label": "Revenu moyen", "value": float(frame["revenu"].mean()), "unit": "XOF"},
            {"label": "Lignes", "value": len(frame)},
        ],
        "series": [
            {
                "label": "Revenu",
                "x": frame["mois"].astype(float).tolist(),
                "y": frame["revenu"].astype(float).tolist(),
            }
        ],
        "tables": [
            {
                "name": "Projection",
                "columns": ["mois", "revenu"],
                "rows": frame.values.tolist(),
            }
        ],
    }
