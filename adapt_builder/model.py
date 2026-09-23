"""Storyboard object model.

The parser turns the .docx into this tree; the builders turn this tree into
Adapt JSON. Nothing here knows about Word, and nothing here knows about Adapt -
that separation is what keeps both halves testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GlossaryTerm:
    """A term marked up inline in the storyboard body copy."""

    slug: str
    text: str
    definition: str = ""

    def as_notify(self) -> dict[str, str]:
        return {"id": self.slug, "title": self.text, "body": self.definition}


@dataclass
class Figure:
    """An image lifted out of the storyboard, with its caption if it had one."""

    index: int
    part_name: str
    ext: str
    data: bytes = field(repr=False, default=b"")
    caption: str = ""
    label: str = ""
    #: Course-relative path, set once the asset destination is known.
    src: str = ""

    @property
    def filename(self) -> str:
        if self.label:
            return f"{self.label}{self.ext}"
        return f"img-{self.index:03d}{self.ext}"


@dataclass
class Callout:
    """A ZOOM IN / QUICK FACT box; becomes ``_hint`` on a sibling component."""

    title: str
    body: str
    icon_class: str
    terms: list[GlossaryTerm] = field(default_factory=list)
    figure: Figure | None = None


@dataclass
class Item:
    """One accordion panel, tab, or hotspot."""

    title: str = ""
    body: str = ""
    tab_title: str = ""
    terms: list[GlossaryTerm] = field(default_factory=list)
    figure: Figure | None = None
    #: ``(kind, html)`` fragments collected while parsing; rendered into ``body``.
    chunks: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class Option:
    """One MCQ answer option."""

    text: str
    correct: bool = False
    #: The storyboard emboldens the correct option. That is an authoring
    #: marker, not learner-facing copy, so it is stripped from ``text`` and
    #: kept here to cross-check the answer key.
    marked: bool = False


@dataclass
class Question:
    body: str
    options: list[Option] = field(default_factory=list)
    select_all: bool = False
    terms: list[GlossaryTerm] = field(default_factory=list)

    #: ``mcq``, ``matching`` or ``selectchoice``. The latter two are authored
    #: as tables rather than as CYP-Answer paragraphs.
    #: A matching question is authored as a table
    #: rather than as CYP-Answer paragraphs, so it carries its pairs below
    #: instead of ``options``.
    kind: str = "mcq"
    #: ``(letter, text)`` for each lettered stem a learner chooses between.
    stems: list[tuple[str, str]] = field(default_factory=list)
    #: The subjects being matched, in the order the table lists them.
    match_options: list[str] = field(default_factory=list)
    #: letter of a stem -> the subject that belongs to it. Keyed by letter
    #: because two stems may share one subject ("Secondary outcome" twice),
    #: which keying by subject would collapse. Some storyboards fill this in on
    #: the Check Your Progress copy of the table as well as on the Answers
    #: copy; the Answers copy is authoritative either way.
    match_answers: dict[str, str] = field(default_factory=dict)
    #: Whether the Answers copy of this question's table has been read. Kept
    #: apart from ``match_answers`` so a question already answered in the CYP
    #: section still consumes its slot in the answer key.
    match_reconciled: bool = False

    #: selectchoice only: the column headings a learner picks between, and one
    #: ``(statement, answer)`` per row. ``answer`` is the 1-based index of the
    #: correct choice, or 0 where every choice applies.
    choices: list[str] = field(default_factory=list)
    grid_items: list[tuple[str, int]] = field(default_factory=list)

    @property
    def selectable(self) -> int:
        n = sum(1 for o in self.options if o.correct)
        return max(n, 1) if self.select_all else 1

    @property
    def is_answered(self) -> bool:
        if self.kind == "matching":
            return bool(self.match_answers)
        if self.kind == "selectchoice":
            return bool(self.grid_items)
        return any(o.correct for o in self.options)


@dataclass
class Component:
    """A leaf node destined for components.json."""

    kind: str  # text | graphic | accordion | tabs | hotgraphic | mcq | ...
    title: str = ""
    display_title: str = ""
    body: str = ""
    instruction: str = ""
    classes: str = ""
    layout: str = "full"
    items: list[Item] = field(default_factory=list)
    terms: list[GlossaryTerm] = field(default_factory=list)
    figure: Figure | None = None
    hint: Callout | None = None
    question: Question | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    #: Components that carry no authored copy but are still required output.
    CONTENTLESS_KINDS = frozenset({"assessmentResults", "pageNav", "media"})

    def is_empty(self) -> bool:
        if self.kind in self.CONTENTLESS_KINDS:
            return False
        if self.kind == "graphic":
            return not self.extra.get("src")
        return not (self.body or self.items or self.figure or self.question)


@dataclass
class Block:
    title: str = ""
    display_title: str = ""
    components: list[Component] = field(default_factory=list)

    def is_empty(self) -> bool:
        return all(c.is_empty() for c in self.components)


@dataclass
class Article:
    title: str = ""
    display_title: str = ""
    blocks: list[Block] = field(default_factory=list)
    is_assessment: bool = False
    assessment_id: str = ""
    score_to_pass: int = 0
    page_level_progress: bool | None = None

    def is_empty(self) -> bool:
        return all(b.is_empty() for b in self.blocks)


@dataclass
class Page:
    slug: str
    title: str = ""
    display_title: str = ""
    articles: list[Article] = field(default_factory=list)
    is_chapter: bool = False
    #: True when the page was invented to hold content found before any
    #: Heading 1 - cover art, logos - which is dropped rather than published.
    implicit: bool = False


@dataclass
class Storyboard:
    #: Course title as authored, e.g. ``Attruby® Product Module``.
    title: str = ""
    pages: list[Page] = field(default_factory=list)
    glossary: list[GlossaryTerm] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    figures: list[Figure] = field(default_factory=list)
    #: Narration / on-screen-text scripts for the Key Concepts videos. The
    #: build cannot produce the videos, so it publishes their specification.
    scripts: list[dict[str, str]] = field(default_factory=list)
    #: Images the build made rather than extracted (filename -> bytes), such as
    #: a hot-spot backdrop composed from several photos. Written with the figures.
    generated_images: dict[str, bytes] = field(default_factory=dict)
