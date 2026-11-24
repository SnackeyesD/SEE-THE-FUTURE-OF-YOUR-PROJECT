"""Rapports déterministes de See The Future.

Ce paquet ne lance aucune simulation et ne calcule aucun agrégat métier : il
met en forme des faits déjà produits par le moteur et déjà persistés par le
stockage. C'est une vue dérivée au sens de *Designing Data-Intensive
Applications* (chapitres 11–12) : elle est reconstructible depuis la source de
vérité, sans second calculateur.
"""

from .formatting import format_date, format_money, format_number, format_ratio
from .markdown import build_markdown
from .models import ReportBranch, ReportInput, ReportProject, ReportVersion
from .pdf import build_pdf, markdown_to_pdf

__version__ = "0.1.0"

__all__ = [
    "ReportBranch",
    "ReportInput",
    "ReportProject",
    "ReportVersion",
    "build_markdown",
    "build_pdf",
    "markdown_to_pdf",
    "format_date",
    "format_money",
    "format_number",
    "format_ratio",
]
