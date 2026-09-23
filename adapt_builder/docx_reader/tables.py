"""Storyboard tables -> Adapt content.

A storyboard table is one of four things, and which one it is decides the
component it becomes:

``glossary``
    the Glossary page's term/definition table (handled by the parser, which
    also pre-scans it so inline terms can find their definitions);
``narration``
    a ``Narration | On Screen Text`` script for a Key Concepts video - not
    learner-facing copy, but the spec for a video someone still has to produce;
``matching``
    a Check Your Progress pairing exercise, restated in the Answers section
    with the answer letters filled in;
``data``
    everything else - a real table of content that ships as HTML.

Classification is by content, not position, because storyboards disagree about
where they put things. Anything unrecognised falls through to ``data``, which
is the safe default: the content ships and can be restyled by hand, rather
than being silently dropped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from docx.table import Table, _Cell
from docx.oxml.ns import qn

from .. import config
from ..model import GlossaryTerm
from .inline import InlineRenderer, clean_html, paragraphs_to_html

#: "A. Indicated to reduce proteinuria..." - a lettered stem in a matching
#: table. The letter is the key the Answers table refers to.
RE_STEM_LETTER = re.compile(r"^\s*([A-H])\s*[.):]\s*(.+)$", re.S)

#: A lone answer letter in its own cell, as the Answers copy of the table has.
RE_LONE_LETTER = re.compile(r"^\s*([A-H])\s*[.)]?\s*$")

#: "Figure 1-3: ..." / "Table 1-1: ..." - a caption that names its own kind.
RE_CAPTION_KIND = re.compile(r"^\s*(figure|table)\b", re.I)


#: A tick in a grid question. Storyboards write it as an X or a checkmark.
RE_TICK = re.compile(r"^[\sxX✓✔✖×☒]+$")


@dataclass
class TableRow:
    cells: list[str]
    #: Per-cell grid span, so a merged header cell keeps its width in HTML.
    spans: list[int] = field(default_factory=list)


@dataclass
class ParsedTable:
    kind: str  # data | narration | matching | selectchoice | glossary
    rows: list[TableRow]
    terms: list[GlossaryTerm] = field(default_factory=list)
    #: narration only
    narration: str = ""
    onscreen: str = ""
    #: matching only
    stems: list[tuple[str, str]] = field(default_factory=list)  # (letter, text)
    options: list[str] = field(default_factory=list)
    answers: dict[str, str] = field(default_factory=dict)  # option text -> letter

    @property
    def is_empty(self) -> bool:
        return not any(any(c.strip() for c in r.cells) for r in self.rows)


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def _cell_html(cell: _Cell, renderer: InlineRenderer) -> tuple[str, list[GlossaryTerm]]:
    """Render one cell's paragraphs, preserving its bullets."""
    chunks: list[tuple[str, str]] = []
    terms: list[GlossaryTerm] = []
    for para in cell.paragraphs:
        try:
            style = para.style.name or ""
        except (AttributeError, KeyError):
            style = ""
        rendered = renderer.render(para)
        if not rendered.html:
            continue
        if style in config.STYLE_BULLET_L1 or style in config.STYLE_INTERACT_BULLET:
            kind = "li1"
        elif style in config.STYLE_BULLET_L2:
            kind = "li2"
        elif style in config.STYLE_ORDERED:
            kind = "num"
        else:
            kind = "p"
        chunks.append((kind, rendered.html))
        terms.extend(rendered.terms)

    html = paragraphs_to_html(chunks)
    # A single paragraph needs no <p> wrapper inside a table cell.
    if html.startswith("<p>") and html.endswith("</p>") and html.count("<p>") == 1:
        html = html[3:-4]
    return html, terms


def _grid_span(cell: _Cell) -> int:
    span = cell._tc.tcPr
    if span is None:
        return 1
    el = span.find(qn("w:gridSpan"))
    if el is None:
        return 1
    try:
        return max(1, int(el.get(qn("w:val"))))
    except (TypeError, ValueError):
        return 1


def read_table(table: Table, renderer: InlineRenderer) -> tuple[list[TableRow], list[GlossaryTerm]]:
    """Read a table into rendered HTML rows, de-duplicating merged cells.

    python-docx repeats a horizontally merged cell once per grid column it
    covers. Emitting it once with a ``colspan`` is what keeps the HTML table
    the same shape as the one in the storyboard.
    """
    rows: list[TableRow] = []
    terms: list[GlossaryTerm] = []
    for row in table.rows:
        cells: list[str] = []
        spans: list[int] = []
        seen: set[int] = set()
        for cell in row.cells:
            key = id(cell._tc)
            if key in seen:
                # Same underlying cell as the previous column - already counted.
                if spans:
                    spans[-1] += 1
                continue
            seen.add(key)
            html, found = _cell_html(cell, renderer)
            cells.append(html)
            spans.append(1)
            terms.extend(found)
        # Trust the XML's own gridSpan where it disagrees with the walk above.
        rows.append(TableRow(cells=cells, spans=spans))
    return rows, terms


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def _plain(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html).strip()


def classify(rows: list[TableRow], mode: str) -> str:
    """Which kind of table is this?"""
    if not rows:
        return "data"
    header = [_plain(c).lower() for c in rows[0].cells]

    if any(h.startswith(config.TABLE_NARRATION_HEADERS) for h in header) and any(
        h in config.TABLE_ONSCREEN_HEADERS for h in header
    ):
        return "narration"

    if mode in ("cyp", "answers"):
        if _looks_like_matching(rows):
            return "matching"
        if _tick_columns(rows):
            return "selectchoice"

    return "data"


def _looks_like_matching(rows: list[TableRow]) -> bool:
    """A matching table has a column of ``A.``-lettered stems.

    That lettering is the whole mechanism - the Answers table pairs each row's
    subject with one of those letters - so requiring it keeps ordinary data
    tables that happen to sit under Check Your Progress out.
    """
    if len(rows) < 2 or len(rows[0].cells) < 2:
        return False
    for col in range(len(rows[0].cells)):
        lettered = 0
        for row in rows:
            if col < len(row.cells) and RE_STEM_LETTER.match(_plain(row.cells[col])):
                lettered += 1
        if lettered >= 2:
            return True
    return False


# ---------------------------------------------------------------------------
# Narration / on-screen-text
# ---------------------------------------------------------------------------


def parse_narration(rows: list[TableRow]) -> tuple[str, str]:
    """Split a script table into (narration, on-screen text).

    The header row names the columns; every row below contributes to both. The
    result is not learner copy - it is what the video has to say and show.
    """
    header = [_plain(c).lower() for c in rows[0].cells]
    n_col = next(
        (i for i, h in enumerate(header) if h.startswith(config.TABLE_NARRATION_HEADERS)),
        0,
    )
    o_col = next(
        (i for i, h in enumerate(header) if h in config.TABLE_ONSCREEN_HEADERS),
        1 if len(header) > 1 else 0,
    )
    narration: list[str] = []
    onscreen: list[str] = []
    for row in rows[1:]:
        if n_col < len(row.cells) and row.cells[n_col]:
            narration.append(row.cells[n_col])
        if o_col < len(row.cells) and row.cells[o_col]:
            onscreen.append(row.cells[o_col])
    return "".join(narration), "".join(onscreen)


#: A cell that opens with a plain paragraph and continues with its bullets:
#: "<p>Understanding Achondroplasia</p><ul><li>...</li></ul>".
RE_LEAD_PARAGRAPH = re.compile(r"^\s*<p>(.*?)</p>\s*(.*)$", re.S)


def parse_narration_panels(rows: list[TableRow]) -> list[tuple[str, str]]:
    """The on-screen-text column as ``(panel title, panel body)`` per row.

    Each row of a Key Concepts script is one topic: its on-screen text opens
    with the topic name and continues with the points made about it, which is
    exactly the shape of an accordion panel.
    """
    header = [_plain(c).lower() for c in rows[0].cells]
    o_col = next(
        (i for i, h in enumerate(header) if h in config.TABLE_ONSCREEN_HEADERS),
        1 if len(header) > 1 else 0,
    )
    panels: list[tuple[str, str]] = []
    for row in rows[1:]:
        cell = row.cells[o_col] if o_col < len(row.cells) else ""
        if not _plain(cell):
            continue
        match = RE_LEAD_PARAGRAPH.match(cell)
        if match and _plain(match.group(1)) and match.group(2).strip():
            panels.append((_plain(match.group(1)), match.group(2).strip()))
        else:
            panels.append(("", cell))
    return panels


def narration_title(rows: list[TableRow]) -> str:
    """The section name out of "Narration for Section 1.1 Presentation"."""
    header = [_plain(c) for c in rows[0].cells]
    for cell in header:
        match = re.search(r"narration\s+for\s+(.+)", cell, re.I)
        if match:
            return re.sub(
                r"\s*(presented\s+by\s+\w+|presentation|video)\s*$",
            "",
            match.group(1),
            flags=re.I,
            ).strip()
    return ""


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


def parse_matching(rows: list[TableRow]) -> tuple[list[tuple[str, str]], list[str], dict[str, str]]:
    """Read a matching table into (stems, options, answers).

    ``stems`` are the lettered choices a learner picks from a dropdown,
    ``options`` are the subjects being matched, and ``answers`` maps a letter
    to its subject - filled in only by the Answers copy of the table, which is
    otherwise identical.
    """
    stem_col = _column_of(rows, lambda t: bool(RE_STEM_LETTER.match(t)))
    letter_col = _column_of(rows, lambda t: bool(RE_LONE_LETTER.match(t)), exclude=stem_col)
    option_col = _option_column(rows, exclude={stem_col, letter_col})

    stems: list[tuple[str, str]] = []
    options: list[str] = []
    answers: dict[str, str] = {}

    for row in rows:
        if stem_col is not None and stem_col < len(row.cells):
            match = RE_STEM_LETTER.match(_plain(row.cells[stem_col]))
            if match:
                # Re-strip the letter off the rendered HTML, not the plain text,
                # so trademark superscripts in a stem survive.
                text = re.sub(r"^\s*[A-H]\s*[.):]\s*", "", row.cells[stem_col], count=1)
                stems.append((match.group(1).upper(), clean_html(text)))

        option = ""
        if option_col is not None and option_col < len(row.cells):
            option = clean_html(row.cells[option_col])
        if option:
            options.append(option)
            if letter_col is not None and letter_col < len(row.cells):
                letter = RE_LONE_LETTER.match(_plain(row.cells[letter_col]))
                if letter:
                    answers[letter.group(1).upper()] = option

    return stems, options, answers


def _column_of(rows: list[TableRow], test, exclude: int | None = None) -> int | None:
    """The column whose cells most often satisfy ``test``."""
    width = max((len(r.cells) for r in rows), default=0)
    best: tuple[int, int] | None = None
    for col in range(width):
        if col == exclude:
            continue
        hits = sum(
            1 for r in rows if col < len(r.cells) and test(_plain(r.cells[col]))
        )
        if hits >= 2 and (best is None or hits > best[1]):
            best = (col, hits)
    return best[0] if best else None


def _option_column(rows: list[TableRow], exclude: set[int | None]) -> int | None:
    """The column holding the subjects being matched: the fullest one left."""
    width = max((len(r.cells) for r in rows), default=0)
    best: tuple[int, int] | None = None
    for col in range(width):
        if col in exclude:
            continue
        filled = sum(1 for r in rows if col < len(r.cells) and _plain(r.cells[col]))
        if filled >= 2 and (best is None or filled > best[1]):
            best = (col, filled)
    return best[0] if best else None


# ---------------------------------------------------------------------------
# Data tables -> HTML
# ---------------------------------------------------------------------------


def to_html(rows: list[TableRow], caption: str = "") -> str:
    """Render a data table, using its first row as a header when it reads like one.

    A first row whose cells are all short and none of which start a sentence is
    a header; a table that starts straight into data gets no ``<thead>`` rather
    than a wrong one.
    """
    if not rows:
        return ""

    parts: list[str] = []
    if caption:
        parts.append(f"<p style='text-align: center;'><strong>{caption}</strong></p>")
    parts.append(f"<table class='{config.TABLE_CLASSES}'>")

    body_start = 0
    if _is_header_row(rows):
        parts.append("<thead><tr>")
        parts.extend(_cells("th", rows[0]))
        parts.append("</tr></thead>")
        body_start = 1

    parts.append("<tbody>")
    for row in rows[body_start:]:
        parts.append("<tr>")
        parts.extend(_cells("td", row))
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


def _cells(tag: str, row: TableRow) -> list[str]:
    out: list[str] = []
    for i, cell in enumerate(row.cells):
        span = row.spans[i] if i < len(row.spans) else 1
        attr = f" colspan='{span}'" if span > 1 else ""
        out.append(f"<{tag}{attr}>{cell}</{tag}>")
    return out


def _is_header_row(rows: list[TableRow]) -> bool:
    if len(rows) < 2:
        return False
    first = [_plain(c) for c in rows[0].cells]
    filled = [c for c in first if c]
    if not filled:
        # A leading blank corner cell is the classic shape of a header row.
        return any(_plain(c) for c in rows[0].cells[1:])
    return all(len(c) <= 90 and not c.endswith(".") for c in filled)


# ---------------------------------------------------------------------------
# Select-choice grids
# ---------------------------------------------------------------------------


def _is_tick(text: str) -> bool:
    text = text.strip()
    return bool(text) and bool(RE_TICK.match(text))


def _tick_columns(rows: list[TableRow]) -> list[int]:
    """Columns that hold only ticks or blanks, and at least one tick.

    That shape is what makes a grid question a grid question: a statement per
    row, and a column per choice with an X in the one that applies.
    """
    if len(rows) < 2:
        return []
    width = max(len(r.cells) for r in rows)
    found: list[int] = []
    for col in range(width):
        ticks = 0
        for row in rows[1:]:
            if col >= len(row.cells):
                continue
            text = _plain(row.cells[col])
            if not text:
                continue
            if _is_tick(text):
                ticks += 1
            else:
                ticks = 0
                break
        if ticks:
            found.append(col)
    # One tick column alone is more likely a stray "X" in a data table.
    return found if len(found) >= 2 else []


def parse_selectchoice(
    rows: list[TableRow],
) -> tuple[list[str], list[tuple[str, int]]]:
    """Read a grid question into (choice labels, (statement, answer) rows).

    ``answer`` is the 1-based index of the ticked choice, or ``0`` when a row
    is ticked in every column - which is how the courses encode "both".
    """
    ticks = _tick_columns(rows)
    if not ticks:
        return [], []

    header = rows[0].cells if rows else []
    choices = [
        clean_html(header[col]) if col < len(header) else f"Option {n}"
        for n, col in enumerate(ticks, start=1)
    ]

    width = max(len(r.cells) for r in rows)
    text_cols = [c for c in range(width) if c not in ticks]
    # The statement column is the fullest column that is not a tick column.
    stmt_col = None
    best = 0
    for col in text_cols:
        filled = sum(1 for r in rows[1:] if col < len(r.cells) and _plain(r.cells[col]))
        if filled > best:
            best, stmt_col = filled, col
    if stmt_col is None:
        return choices, []

    items: list[tuple[str, int]] = []
    for row in rows[1:]:
        text = clean_html(row.cells[stmt_col]) if stmt_col < len(row.cells) else ""
        if not text:
            continue
        marked = [
            n
            for n, col in enumerate(ticks, start=1)
            if col < len(row.cells) and _is_tick(_plain(row.cells[col]))
        ]
        if not marked:
            continue
        items.append((text, marked[0] if len(marked) == 1 else 0))
    return choices, items
