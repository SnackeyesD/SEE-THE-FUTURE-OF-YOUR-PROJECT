"""Rendu PDF local, déterministe et sans dépendance.

Le PDF est une **seconde mise en forme** du même Markdown : aucune valeur n'est
recalculée, aucune horloge n'est lue, aucun accès réseau n'est effectué. Deux
appels avec le même ``ReportInput`` produisent exactement les mêmes octets, ce
qui rend l'export vérifiable (DDIA, chapitres 11–12 : une donnée dérivée doit
être reconstructible à partir de sa source).

Le générateur écrit un PDF 1.4 minimal avec les polices standard Helvetica
(encodage WinAnsi) : pas de bibliothèque propriétaire, pas de fichier de police
à embarquer, donc un export qui reste hors ligne et léger.
"""

from __future__ import annotations

import re

from .markdown import build_markdown
from .models import ReportInput

PAGE_W = 595.28
PAGE_H = 841.89
MARGIN_X = 46.0
MARGIN_TOP = 52.0
MARGIN_BOTTOM = 54.0
CONTENT_W = PAGE_W - 2 * MARGIN_X

BODY_SIZE = 9.0
BODY_LEADING = 12.0
SMALL_SIZE = 7.6
SMALL_LEADING = 9.6
HEADING_SIZES = {1: 17.0, 2: 12.5, 3: 10.5}
HEADING_LEADING = {1: 21.0, 2: 16.0, 3: 13.5}

DISCLAIMER_FOOTER = "Simulation basée sur vos hypothèses — pas une prévision garantie."

_NARROW = set("ilI.,:;'!|()[]")
_WIDE = set("mwMW@")


def build_pdf(report: ReportInput) -> bytes:
    """Construit le PDF du dossier depuis les mêmes faits que le Markdown."""

    markdown = build_markdown(report)
    return markdown_to_pdf(markdown, title=f"Dossier de simulation — {report.project.name}")


def markdown_to_pdf(markdown: str, *, title: str = "Dossier de simulation") -> bytes:
    """Rend un Markdown déjà construit en PDF, sans rien réinterpréter."""

    canvas = _Canvas()
    lines = markdown.splitlines()
    index = 0
    while index < len(lines):
        raw = lines[index].rstrip()
        stripped = raw.strip()
        if not stripped:
            canvas.gap(3)
            index += 1
            continue
        if stripped.startswith("```"):
            index += 1
            continue
        if stripped.startswith("|"):
            rows: list[list[str]] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                candidate = lines[index]
                if not _is_separator(candidate):
                    rows.append(_split_row(candidate))
                index += 1
            if rows:
                canvas.table(rows)
            canvas.gap(6)
            continue
        heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading:
            canvas.heading(min(len(heading.group(1)), 3), _plain(heading.group(2)))
            index += 1
            continue
        if stripped.startswith(">"):
            canvas.quote(_plain(stripped.lstrip(">").strip()))
            index += 1
            continue
        bullet = re.match(r"^(\s*)-\s+(.*)$", raw)
        if bullet:
            canvas.bullet(_plain(bullet.group(2)), min(len(bullet.group(1)), 6) * 4)
            index += 1
            continue
        canvas.paragraph(_plain(stripped))
        index += 1
    return canvas.finish(title)


def _plain(text: str) -> str:
    return text.replace("**", "").replace("`", "").replace("\\|", "|").strip()


def _split_row(line: str) -> list[str]:
    inner = line.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|"):
        inner = inner[:-1]
    return [cell.replace("\\|", "|").strip() for cell in re.split(r"(?<!\\)\|", inner)]


def _is_separator(line: str) -> bool:
    cells = [cell.strip() for cell in _split_row(line)]
    return bool(cells) and all(re.fullmatch(r":?-{2,}:?", cell) for cell in cells)


def _text_width(text: str, size: float, bold: bool = False) -> float:
    total = 0.0
    for char in text:
        if char == " ":
            total += 0.28
        elif char in _NARROW:
            total += 0.30
        elif char in _WIDE:
            total += 0.84
        else:
            total += 0.55 if bold else 0.52
    return total * size


def _wrap(text: str, size: float, width: float, bold: bool = False) -> list[str]:
    if not text:
        return [""]
    lines: list[str] = []
    current = ""
    for word in text.split(" "):
        candidate = word if not current else f"{current} {word}"
        if _text_width(candidate, size, bold) <= width:
            current = candidate
            continue
        if current:
            lines.append(current)
        while _text_width(word, size, bold) > width and len(word) > 1:
            cut = len(word)
            while cut > 1 and _text_width(word[:cut], size, bold) > width:
                cut -= 1
            lines.append(word[:cut])
            word = word[cut:]
        current = word
    if current:
        lines.append(current)
    return lines or [""]


def _pdf_text(value: str) -> str:
    cleaned = "".join(char if 32 <= ord(char) < 256 else " " for char in value)
    return cleaned.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


class _Canvas:
    def __init__(self) -> None:
        self.pages: list[list[str]] = []
        self.ops: list[str] = []
        self.y = 0.0
        self._start_page()

    def _start_page(self) -> None:
        self.ops = []
        self.pages.append(self.ops)
        self.y = PAGE_H - MARGIN_TOP

    def new_page(self) -> None:
        self._start_page()

    def ensure(self, height: float) -> None:
        if self.y - height < MARGIN_BOTTOM:
            self.new_page()

    def gap(self, amount: float) -> None:
        self.y -= amount

    def text(
        self,
        x: float,
        y: float,
        value: str,
        size: float,
        *,
        bold: bool = False,
        gray: float = 0.15,
    ) -> None:
        if not value:
            return
        font = "F2" if bold else "F1"
        self.ops.append(
            f"BT {gray:.2f} {gray:.2f} {gray:.2f} rg /{font} {size:.2f} Tf "
            f"1 0 0 1 {x:.2f} {y:.2f} Tm ({_pdf_text(value)}) Tj ET"
        )

    def paragraph(self, text: str) -> None:
        self._lines(text, BODY_SIZE, CONTENT_W, BODY_LEADING, x=MARGIN_X)
        self.gap(2)

    def _lines(
        self,
        text: str,
        size: float,
        width: float,
        leading: float,
        *,
        x: float,
        bold: bool = False,
        gray: float = 0.15,
        prefix: str | None = None,
    ) -> None:
        chunks = _wrap(text, size, width, bold)
        for position, chunk in enumerate(chunks):
            self.ensure(leading)
            self.y -= leading
            if position == 0 and prefix is not None:
                self.text(x, self.y, prefix, size, gray=0.45)
            offset = 10 if prefix is not None else 0
            self.text(x + offset, self.y, chunk, size, bold=bold, gray=gray)

    def heading(self, level: int, text: str) -> None:
        size = HEADING_SIZES[level]
        leading = HEADING_LEADING[level]
        self.gap(6 if level > 1 else 10)
        for chunk in _wrap(text, size, CONTENT_W, True):
            self.ensure(leading)
            self.y -= leading
            self.text(MARGIN_X, self.y, chunk, size, bold=True, gray=0.08)
        self.gap(3)

    def bullet(self, text: str, indent: float) -> None:
        self._lines(
            text,
            BODY_SIZE,
            CONTENT_W - indent - 10,
            BODY_LEADING,
            x=MARGIN_X + indent,
            prefix="•",
        )
        self.gap(1)

    def quote(self, text: str) -> None:
        chunks = _wrap(text, BODY_SIZE, CONTENT_W - 12, False)
        for chunk in chunks:
            self.ensure(BODY_LEADING)
            self.y -= BODY_LEADING
            self.ops.append(
                f"0.82 0.82 0.82 RG 0.8 w {MARGIN_X + 2:.2f} {self.y - 2:.2f} m "
                f"{MARGIN_X + 2:.2f} {self.y + BODY_SIZE - 1:.2f} l S"
            )
            self.text(MARGIN_X + 10, self.y, chunk, BODY_SIZE, gray=0.32)
        self.gap(3)

    def table(self, rows: list[list[str]]) -> None:
        columns = max(len(row) for row in rows)
        padded = [row + [""] * (columns - len(row)) for row in rows]
        weights = []
        for index in range(columns):
            longest = max(len(_plain(row[index])) for row in padded)
            weights.append(min(max(longest, 4), 34))
        scale = CONTENT_W / sum(weights)
        widths = [weight * scale for weight in weights]
        size = SMALL_SIZE if columns > 4 else 8.2
        leading = SMALL_LEADING if columns > 4 else 10.4
        header, *body = padded
        self._table_row(header, widths, size, leading, bold=True, shade=True)
        for row in body:
            if self.y - (leading + 4) < MARGIN_BOTTOM:
                self.new_page()
                self._table_row(header, widths, size, leading, bold=True, shade=True)
            self._table_row(row, widths, size, leading)

    def _table_row(
        self,
        cells: list[str],
        widths: list[float],
        size: float,
        leading: float,
        *,
        bold: bool = False,
        shade: bool = False,
    ) -> None:
        wrapped = [
            _wrap(_plain(cell), size, width - 6, bold)
            for cell, width in zip(cells, widths, strict=True)
        ]
        height = max(len(lines) for lines in wrapped) * leading + 5
        self.ensure(height)
        if shade:
            self.ops.append(
                f"0.93 0.93 0.93 rg {MARGIN_X:.2f} {self.y - height:.2f} "
                f"{CONTENT_W:.2f} {height:.2f} re f"
            )
        x = MARGIN_X
        top = self.y - size - 2
        for lines, width in zip(wrapped, widths, strict=True):
            for offset, chunk in enumerate(lines):
                self.text(x + 3, top - offset * leading, chunk, size, bold=bold, gray=0.12)
            x += width
        self.y -= height
        self.ops.append(
            f"0.82 0.82 0.82 RG 0.6 w {MARGIN_X:.2f} {self.y:.2f} m "
            f"{MARGIN_X + CONTENT_W:.2f} {self.y:.2f} l S"
        )

    def finish(self, title: str) -> bytes:
        total = len(self.pages)
        for number, ops in enumerate(self.pages, start=1):
            ops.append(
                f"0.55 0.55 0.55 RG 0.5 w {MARGIN_X:.2f} {MARGIN_BOTTOM - 14:.2f} m "
                f"{MARGIN_X + CONTENT_W:.2f} {MARGIN_BOTTOM - 14:.2f} l S"
            )
            ops.append(
                f"BT 0.45 0.45 0.45 rg /F1 7 Tf 1 0 0 1 {MARGIN_X:.2f} "
                f"{MARGIN_BOTTOM - 26:.2f} Tm ({_pdf_text(DISCLAIMER_FOOTER)}) Tj ET"
            )
            label = f"Page {number} / {total}"
            ops.append(
                f"BT 0.45 0.45 0.45 rg /F1 7 Tf 1 0 0 1 "
                f"{MARGIN_X + CONTENT_W - _text_width(label, 7):.2f} "
                f"{MARGIN_BOTTOM - 26:.2f} Tm ({_pdf_text(label)}) Tj ET"
            )
        return _assemble(self.pages, title)


def _assemble(pages: list[list[str]], title: str) -> bytes:
    catalog_id = 1
    pages_id = 2
    regular_id = 3
    bold_id = 4
    next_id = 5
    objects: dict[int, bytes] = {}
    kids: list[int] = []

    for ops in pages:
        stream = "\n".join(ops).encode("cp1252", "replace")
        content_id = next_id
        page_id = next_id + 1
        next_id += 2
        kids.append(page_id)
        objects[content_id] = (
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"\nendstream"
        )
        objects[page_id] = (
            f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {PAGE_W:.2f} {PAGE_H:.2f}] "
            f"/Resources << /Font << /F1 {regular_id} 0 R /F2 {bold_id} 0 R >> >> "
            f"/Contents {content_id} 0 R >>"
        ).encode("ascii")

    info_id = next_id
    objects[catalog_id] = f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode("ascii")
    objects[pages_id] = (
        f"<< /Type /Pages /Kids [{' '.join(f'{kid} 0 R' for kid in kids)}] "
        f"/Count {len(pages)} >>"
    ).encode("ascii")
    objects[regular_id] = (
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
    )
    objects[bold_id] = (
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold "
        b"/Encoding /WinAnsiEncoding >>"
    )
    objects[info_id] = (
        f"<< /Title ({_pdf_text(title)}) /Author (See The Future) "
        f"/Creator (See The Future) /Producer (see-reporting) >>"
    ).encode("cp1252", "replace")

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: dict[int, int] = {}
    for object_id in range(1, info_id + 1):
        payload = objects[object_id]
        offsets[object_id] = len(out)
        out += f"{object_id} 0 obj\n".encode("ascii") + payload + b"\nendobj\n"

    xref = len(out)
    out += f"xref\n0 {info_id + 1}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for object_id in range(1, info_id + 1):
        out += f"{offsets[object_id]:010d} 00000 n \n".encode("ascii")
    out += (
        f"trailer\n<< /Size {info_id + 1} /Root {catalog_id} 0 R /Info {info_id} 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n"
    ).encode("ascii")
    return bytes(out)
