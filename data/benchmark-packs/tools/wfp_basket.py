"""Recalcule le panier de référence du pack CG depuis les prix WFP/HDX.

Le script ne fabrique aucune valeur : il agrège les prix de détail publiés par
le PAM pour Brazzaville. Il sert à documenter et à rejouer le sourcing du
``unit_price`` du pack ``cg-brazzaville-retail-2026.2``.

Exemple :
    uv run --project packages/benchmarks python \\
        data/benchmark-packs/tools/wfp_basket.py --months 12 --json
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import statistics
import urllib.request
from collections.abc import Iterable
from pathlib import Path
from typing import Any

WFP_CONGO_CSV = (
    "https://data.humdata.org/dataset/86dfc591-9de6-44f8-b908-ebba34a96ddf/"
    "resource/21bf778a-2cdd-4ca2-b017-9779534d3281/download/wfp_food_prices_cog.csv"
)

#: Composants du panier et quantités, alignés sur ``referenceBasket``.
BASKET = {
    "Rice (mixed, low quality)": 5.0,
    "Cassava flour": 5.0,
    "Beans (white)": 3.0,
    "Oil (vegetable)": 2.0,
    "Salt": 1.0,
}


def load_rows(source: Path | None) -> list[dict[str, str]]:
    if source is None:
        with urllib.request.urlopen(WFP_CONGO_CSV, timeout=60) as response:
            payload = response.read().decode("utf-8")
        return list(csv.DictReader(io.StringIO(payload)))
    return list(csv.DictReader(source.open(encoding="utf-8")))


def monthly_baskets(rows: Iterable[dict[str, str]]) -> list[tuple[str, float]]:
    """Somme mensuelle du panier, uniquement si les cinq produits sont présents."""

    prices: dict[tuple[str, str], float] = {}
    for row in rows:
        if row["admin1"] != "Brazzaville":
            continue
        commodity = row["commodity"]
        if commodity not in BASKET:
            continue
        prices[(row["date"], commodity)] = float(row["price"])

    dates = sorted({date for date, _ in prices})
    baskets: list[tuple[str, float]] = []
    for date in dates:
        if any((date, commodity) not in prices for commodity in BASKET):
            continue
        total = sum(
            prices[(date, commodity)] * quantity
            for commodity, quantity in BASKET.items()
        )
        baskets.append((date, total))
    return baskets


def summarise(baskets: list[tuple[str, float]], months: int) -> dict[str, Any]:
    window = baskets[-months:]
    if not window:
        raise SystemExit("aucun mois complet dans la série WFP")
    values = [value for _, value in window]
    return {
        "months": len(window),
        "firstMonth": window[0][0],
        "lastMonth": window[-1][0],
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
        "monthly": {date: round(value, 2) for date, value in window},
        "source": WFP_CONGO_CSV,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=None)
    parser.add_argument("--months", type=int, default=12)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = summarise(monthly_baskets(load_rows(args.csv)), max(1, args.months))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(
        f"Panier sur {result['months']} mois "
        f"({result['firstMonth']} → {result['lastMonth']})"
    )
    print(f"médiane : {result['median']:.0f} XAF")
    print(f"min/max : {result['min']:.0f} / {result['max']:.0f} XAF")
    for date, value in result["monthly"].items():
        print(f"  {date} : {value:.0f} XAF")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
