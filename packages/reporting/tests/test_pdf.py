from __future__ import annotations

import re

from test_markdown import _payload

from see_reporting import ReportInput, build_markdown, build_pdf, markdown_to_pdf


def test_pdf_is_deterministic() -> None:
    report = ReportInput.model_validate(_payload())
    assert build_pdf(report) == build_pdf(report)


def test_pdf_has_a_valid_structure() -> None:
    report = ReportInput.model_validate(_payload())
    content = build_pdf(report)
    assert content.startswith(b"%PDF-1.4")
    assert content.rstrip().endswith(b"%%EOF")
    assert b"/Type /Catalog" in content
    assert b"/Type /Pages" in content
    assert b"/Type /Page " in content
    assert b"Helvetica" in content

    pages = int(re.search(rb"/Count (\d+)", content).group(1))
    assert pages >= 1
    assert content.count(b"/Type /Page ") == pages


def test_pdf_contains_the_report_text() -> None:
    report = ReportInput.model_validate(_payload())
    text = build_markdown(report)
    assert "Traçabilité" in text
    content = build_pdf(report).decode("cp1252", "replace")
    assert "Dossier de simulation" in content
    assert "Traçabilité" in content
    assert "run-123" in content


def test_pdf_has_no_local_path_or_secret() -> None:
    content = build_pdf(ReportInput.model_validate(_payload())).decode("cp1252", "replace")
    assert "C:\\" not in content
    assert "/home/" not in content
    assert "/Users/" not in content
    assert "sk-" not in content
    assert "api_key" not in content.lower()


def test_markdown_to_pdf_handles_accents_and_long_cells() -> None:
    markdown = (
        "# Dossier — Dépôt\n\n"
        "| Hypothèse | Valeur |\n|---|---|\n"
        "| Trésorerie minimale P50 | 1 234 567 FCFA |\n"
        "| " + "libellé très long " * 20 + " | 42 |\n\n"
        "- élément accentué : éàçù\n"
        "> Simulation basée sur vos hypothèses.\n"
    )
    content = markdown_to_pdf(markdown)
    assert content.startswith(b"%PDF-1.4")
    decoded = content.decode("cp1252", "replace")
    assert "Dépôt" in decoded
    assert "Trésorerie minimale P50" in decoded
    assert "éàçù" in decoded
    assert "—" in decoded


def test_pdf_escapes_parentheses_in_metadata() -> None:
    content = markdown_to_pdf("# Rapport\n\nok\n", title="Dossier (provisoire)")
    assert b"/Title (Dossier \\(provisoire\\))" in content
