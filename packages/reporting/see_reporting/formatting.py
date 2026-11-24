"""Mise en forme pure, sans calcul métier.

Les fonctions ci-dessous ne produisent aucun agrégat : elles arrondissent et
séparent les chiffres déjà calculés par le moteur. Une valeur absente reste
explicitement « non disponible », jamais zéro (règle produit V3).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from typing import TypeVar

T = TypeVar("T")


def _decimal_comma(text: str) -> str:
    return text.replace(".", ",")


def format_number(value: float, decimals: int = 0) -> str:
    if decimals <= 0:
        text = f"{value:,.0f}"
    else:
        text = f"{value:,.{decimals}f}"
    return _decimal_comma(text.replace(",", " "))


def format_money(value: float, currency: str, decimals: int = 0) -> str:
    return f"{format_number(value, decimals)} {currency}"


def format_ratio(value: float, decimals: int = 1) -> str:
    return f"{format_number(value * 100, decimals)} %"


def format_signed(value: float, currency: str) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{format_money(value, currency)}"


def format_date(value: str | None) -> str:
    if not value:
        return "non disponible"
    try:
        if "T" in value:
            return datetime.fromisoformat(value).date().strftime("%d/%m/%Y")
        return date.fromisoformat(value).strftime("%d/%m/%Y")
    except ValueError:
        return value


def format_optional(value: T | None, render: Callable[[T], str]) -> str:
    if value is None:
        return "non disponible"
    return render(value)
