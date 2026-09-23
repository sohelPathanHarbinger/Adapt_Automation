"""Storyboard .docx -> :class:`adapt_builder.model.Storyboard`.

The storyboard is rigorously styled, so parsing is a state machine over
paragraph styles rather than guesswork over text:

    Heading 1                 -> page (contentObject)
    Heading 2                 -> article
    Heading 3/4/5             -> block
    Normal / Bullet list ...  -> body copy, accumulated into a text component
    Interactivity-Heading-1   -> starts an accordion / tabs / hotgraphic / callout
    Interactivity-Heading-2   -> one accordion panel, tab or hotspot
    CYP-Question / CYP - ...  -> Check Your Progress questions and options
    il Reference              -> reference list entries

Two articles are handled specially: "Check Your Progress" collects questions,
and the "Answers" section that follows it is an answer key for those questions
rather than a page article of its own.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

import docx
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from .. import config
from ..model import (
    Article,
    Block,
    Callout,
    Component,
    Figure,
    GlossaryTerm,
    Item,
    Option,
    Page,
    Question,
    Storyboard,
)
from ..report import Report
from . import tables
from .images import ImageRecord, compose_panels, compose_stack, extract_images
from .inline import InlineRenderer, clean_html, paragraphs_to_html, slugify_term
from .title import extract_title

#: "Accordion 1: ...", "Tab 2 - ...", "Hot spot 3. ...". An emboldened heading
#: arrives as "<strong>Accordion 1: ...</strong>", so the opening tags are
#: matched and kept while the numbering between them is dropped.
RE_ITEM_PREFIX = re.compile(
    r"^(\s*(?:<(?:strong|em|b|i)>\s*)*)"
    r"(?:accordion|tabs?|hot\s?spot)\s*\d+\s*(?:[:.\-]\s*|$)",
    re.I,
)
#: An answer key is a letter set or True/False. Storyboards decorate it in two
#: ways that carry no meaning for the key itself: a superscript reference
#: marker ("A<sup>5</sup>"), and a sentence of rationale after the answer
#: ("False. INGREZZA is available in both..."). Both are allowed and ignored.
RE_ANSWER_KEY = re.compile(
    r"^\s*(?:(true|false)|([A-H](?:\s*(?:,|and|&)\s*[A-H])*))"
    r"\s*(?:[.;:\)]\s*.*)?$",
    re.I | re.S,
)

#: Superscript reference markers, which sit inside or right after the key.
RE_SUP = re.compile(r"<sup>.*?</sup>", re.I | re.S)
RE_SELECT_ALL = re.compile(r"select all that apply", re.I)
#: "True or false? Spinal stenosis is ..." - a stem, even though it ends in a
#: full stop rather than the question mark.
RE_TRUE_FALSE_STEM = re.compile(r"^\s*true\s+or\s+false\b", re.I)
#: "Put the following events in the correct chronological order." Its key is a
#: sequence of letters, so it is built as a matching question.
RE_ORDERING = re.compile(r"\b(?:correct|chronological|right|proper)\s+(?:\w+\s+)?order\b", re.I)
ORDINALS = ("First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh", "Eighth")
#: Narration titles that name no section ("Narration for KCs ...").
GENERIC_NARRATION_SLUGS = frozenset({"kcs", "kc", "key-concepts"})
#: "[Programming Note: Horizontal Tabs]" / "[Style: Programming-Note]" inside
#: an interactivity label is an aside; "[Vertical] Tabs" is part of the type.
RE_LABEL_BRACKET = re.compile(r"\[([^\]]*)\]")
RE_LABEL_ASIDE = re.compile(r"program|style|note|:", re.I)
#: A whole paragraph that stands in for media someone still has to make:
#: "{Animation: MOA of Infigratinib}", "[Illustration/animation]".
RE_PLACEHOLDER = re.compile(r"^\s*[\[{]\s*(?:animation|illustration)[^\]}]*[\]}]\s*$", re.I)
#: A paragraph that is nothing but a URL - the source of a stock image.
RE_BARE_URL = re.compile(r"^\s*https?://\S+\s*$", re.I)
#: Leading dingbats and stray punctuation. "<" is excluded so an opening
#: HTML tag is never mistaken for decoration and half-eaten.
RE_SYMBOL_PREFIX = re.compile(r"^[^\w(<]+")
RE_BLANK_RUN = re.compile(r"_{3,}")
#: "7. In PROPEL 3, ..." / "4.\tB" - a question number the author typed. It
#: repeats the position the build already knows, so it is dropped. Any leading
#: markup is kept, so an emboldened stem stays emboldened.
RE_QUESTION_NUMBER = re.compile(r"^(\s*(?:<[^>]+>\s*)*)\d{1,2}[.)]\s+")


def _drop_numbering(text: str) -> str:
    return RE_QUESTION_NUMBER.sub(r"\1", text, count=1).strip()


def _looks_like_question(raw: str) -> bool:
    """Does this read as a question stem rather than an answer option?"""
    text = raw.strip()
    if not text:
        return False
    return bool(
        text.endswith("?")
        or RE_BLANK_RUN.search(text)
        or RE_SELECT_ALL.search(text)
        or RE_TRUE_FALSE_STEM.match(text)
    )


#: Interactivity kinds whose panels are answer data rather than content. They
#: get no synthesised lead-in panel, because the first heading under the label
#: is already the first option or setting.
QUESTION_INTERACTIVITIES = frozenset({"gmcq", "slider", "textinput"})


def _interactivity_label(raw: str) -> tuple[str, str] | None:
    """Read an interactivity label, in whichever form the storyboard uses.

    Two conventions are in circulation and both appear across these courses::

        Interactivity: Vertical Tabs      -> ("vertical tabs", "")
        Accordion: Learning Objectives    -> ("accordion", "Learning Objectives")

    The second form names the interactivity's own heading after the type, so
    the type has to be recognised before the colon rather than after it.
    Returns ``None`` when the paragraph is not a label at all.
    """
    text = raw.strip()
    if ":" not in text:
        return None
    head, tail = text.split(":", 1)
    head = head.strip().lower()
    # Drop bracketed asides, keep bracketed type words: "[Vertical ] Tabs".
    tail = RE_LABEL_BRACKET.sub(
        lambda m: " " if RE_LABEL_ASIDE.search(m.group(1)) else f" {m.group(1)} ",
        tail,
    )
    tail = " ".join(tail.split())

    if head == config.INTERACTIVITY_PREFIX.rstrip(":"):
        return tail.lower(), ""
    if head in config.INTERACTIVITY_ALT_TYPES:
        return head, tail
    return None


def slugify(text: str, max_words: int = 5) -> str:
    words = re.sub(r"[^A-Za-z0-9\s-]", " ", text).split()
    return "-".join(words[:max_words]).lower().strip("-") or "page"


def iter_body(document) -> list[Paragraph | Table]:
    """Yield paragraphs and tables of the document body in reading order."""
    out: list[Paragraph | Table] = []
    for child in document.element.body.iterchildren():
        if child.tag == qn("w:p"):
            out.append(Paragraph(child, document))
        elif child.tag == qn("w:tbl"):
            out.append(Table(child, document))
    return out


def _style(item) -> str:
    try:
        return item.style.name or ""
    except (AttributeError, KeyError):
        return ""


class StoryboardParser:
    def __init__(
        self, path: Path, report: Report, originals: Path | None = None
    ) -> None:
        self.path = path
        self.report = report
        self.document = docx.Document(str(path))
        self.body = iter_body(self.document)

        self.images, orphans = extract_images(path, originals=originals)
        if orphans:
            self.report.note(
                f"{len(orphans)} unreferenced media part(s) left in the .docx "
                "(stale Word revisions), not extracted"
            )

        self._media_index = self._build_media_index()

        self.sb = Storyboard()
        self.sb.title, title_source = extract_title(self.document, path)
        self.report.note(f"course title '{self.sb.title}' taken from {title_source}")

        self.glossary_lookup = self._prescan_glossary()
        self.renderer = InlineRenderer(self.glossary_lookup)

        # Cursor state
        self.page: Page | None = None
        self.article: Article | None = None
        self.block: Block | None = None
        self.mode = "body"  # body | cyp | answers | references | glossary

        # Buffers
        self.text_chunks: list[tuple[str, str]] = []
        self.text_terms: list[GlossaryTerm] = []
        #: A "Table 1-1: ..." caption waiting for the table it names.
        self.pending_caption = ""
        #: Set by an "Interactivity: Table" label: the next table becomes a
        #: table component rather than HTML inside the surrounding copy.
        self.pending_table_component = False
        self.interactivity: dict | None = None
        self.pending_callout: Callout | None = None
        self.questions: list[Question] = []
        self.cyp_article: Article | None = None
        self.answer_index = 0
        self.assessment_count = 0
        #: The CYP style of the previous paragraph, which is what tells a
        #: question stem apart from an option styled like one.
        self.last_cyp_style = ""
        #: Heading level (3-5) of the open block. A deeper heading arriving
        #: before the block has any copy becomes a sub-heading inside it, so
        #: "PROPEL 2 Results" is not lost above "Baseline Demographics".
        self.block_level = 0
        self.pending_subheading = ""
        #: Figures pasted inside a list item: emitted after the list, so the
        #: picture does not cut the list in two.
        self.deferred_graphics: list[ImageRecord] = []
        #: ``(block, component index, note)`` per "side by side" programming note.
        self.side_by_side: list[tuple[Block, int, str]] = []
        #: Programming notes this build carried out, so the report does not list
        #: them as still to do.
        self.notes_done: set[str] = set()
        self.how_to_built = False

    # ------------------------------------------------------------------
    # Pre-scan: the glossary table must be known before body copy renders,
    # because inline terms pull their definitions from it.
    # ------------------------------------------------------------------

    def _prescan_glossary(self) -> dict[str, str]:
        lookup: dict[str, str] = {}
        in_glossary = False
        for item in self.body:
            if isinstance(item, Paragraph):
                if _style(item) in config.STYLE_PAGE:
                    in_glossary = item.text.strip().lower() == config.TITLE_GLOSSARY
            elif in_glossary:
                for row in item.rows:
                    cells = row.cells
                    if len(cells) < 2:
                        continue
                    term = _cell_text(cells[0])
                    definition = _cell_text(cells[1])
                    if term:
                        lookup[term.lower()] = definition
                        self.sb.glossary.append(
                            GlossaryTerm(
                                slug=slugify_term(term),
                                text=term,
                                definition=definition,
                            )
                        )
                in_glossary = False
        return lookup

    # ------------------------------------------------------------------
    # Figure lookup
    # ------------------------------------------------------------------

    def _build_media_index(self) -> dict[str, list[ImageRecord]]:
        """media part name -> its records, in document order.

        A bitmap reused across the storyboard has one record per occurrence, so
        popping from the front of the list keeps each occurrence's own caption.
        """
        index: dict[str, list[ImageRecord]] = {}
        for rec in self.images:
            index.setdefault(rec.media, []).append(rec)
        return index

    def _resolve_rid(self, rid: str) -> ImageRecord | None:
        """Map a drawing's relationship id to its extracted image record."""
        try:
            part = self.document.part.rels[rid].target_part
        except (KeyError, ValueError):
            self.report.warn(f"drawing relationship '{rid}' could not be resolved")
            return None

        media = str(part.partname).lstrip("/")
        queue = self._media_index.get(media)
        if not queue:
            self.report.warn(f"image '{media}' is in the document but was not extracted")
            return None
        # Keep the first record available for any later reuse of the same bitmap.
        return queue.pop(0) if len(queue) > 1 else queue[0]

    def _figure_src(self, rid: str) -> tuple[str, str]:
        rec = self._resolve_rid(rid)
        if rec is None:
            return "", ""
        return rec.src, (rec.alt or rec.title)

    # ------------------------------------------------------------------
    # Structure helpers
    # ------------------------------------------------------------------

    def _ensure_page(self) -> Page:
        if self.page is None:
            self.page = Page(
                slug="untitled", title="Untitled", display_title="", implicit=True
            )
            self.sb.pages.append(self.page)
        return self.page

    def _ensure_article(self) -> Article:
        if self.article is None:
            page = self._ensure_page()
            self.article = Article(title=page.title, display_title="")
            page.articles.append(self.article)
        return self.article

    def _ensure_block(self) -> Block:
        if self.block is None:
            article = self._ensure_article()
            self.block = Block()
            article.blocks.append(self.block)
        return self.block

    def _add_component(self, component: Component) -> Component:
        block = self._ensure_block()
        if self.pending_subheading:
            heading = f"<h4>{html.escape(self.pending_subheading, quote=False)}</h4>"
            self.pending_subheading = ""
            if component.kind == "text":
                component.body = heading + component.body
            else:
                block.components.append(Component(kind="text", title="", body=heading))
        block.components.append(component)
        if self.pending_callout is not None:
            component.hint = self.pending_callout
            self.pending_callout = None
        return component

    # ------------------------------------------------------------------
    # Buffer flushing
    # ------------------------------------------------------------------

    def _flush_text(self) -> None:
        body = paragraphs_to_html(self.text_chunks) if self.text_chunks else ""
        terms = self.text_terms
        self.text_chunks = []
        self.text_terms = []
        if body:
            self._add_component(Component(kind="text", title="", body=body, terms=terms))
        deferred, self.deferred_graphics = self.deferred_graphics, []
        for rec in deferred:
            self._add_graphic_record(rec)

    def _flush_interactivity(self) -> None:
        inter = self.interactivity
        if inter is None:
            return
        self.interactivity = None

        kind = inter["kind"]
        items: list[Item] = inter["items"]

        if kind == "callout":
            self._flush_callout(inter)
            return

        for item in items:
            item.body = paragraphs_to_html(item.chunks)

        items = [i for i in items if i.body or i.title or i.figure]

        lead = paragraphs_to_html(inter["lead_chunks"])

        if kind == "textinput":
            # Each panel is one accepted answer; alternatives are separated by
            # "/" or "," within it, because a typed answer has spellings.
            component = Component(kind=kind, title=inter["label"], body=lead)
            component.extra["answers"] = [
                [part.strip() for part in re.split(r"[/,]", item.title) if part.strip()]
                for item in items
                if item.title.strip()
            ]
            self._add_component(component)
            self.report.count("questions")
            return

        if kind == "slider":
            component = Component(kind=kind, title=inter["label"], body=lead)
            component.extra.update(_slider_settings(items, self.report))
            self._add_component(component)
            self.report.count("questions")
            return

        if kind == "gmcq":
            # A picture-answer question authored as an interactivity: each
            # panel is one option, and the bolded one is the answer. It has no
            # Answers section to check against, so the bolding is all there is.
            question = Question(body=lead)
            for item in items:
                text, marked = _strip_answer_marker(item.title)
                question.options.append(
                    Option(text=text or item.title, correct=marked, marked=marked)
                )
            component = Component(
                kind=kind,
                title=inter["label"],
                body=question.body,
                question=question,
                terms=inter["terms"],
            )
            self._add_component(component)
            self.report.count("questions")
            return

        lead_body = lead
        if not items and lead_body:
            # An interactivity whose panels were never marked up: its lead copy
            # is the whole of it, so publish it as a single panel rather than
            # dropping the content.
            items = [_new_item(title=inter["label"])]
            items[0].body = lead_body
            lead_body = ""

        if not items:
            self.report.warn(
                f"'{inter['label']}' produced no items "
                f"(page '{self.page.title if self.page else '?'}')"
            )
            return

        component = Component(
            kind=kind,
            title=inter["label"],
            body=lead_body,
            items=items,
            terms=inter["terms"],
            figure=inter.get("figure"),
        )
        if kind == "tabs":
            component.extra["_tabLayout"] = inter["tab_layout"]
        if kind == "hotgraphic":
            component.extra["attribution"] = inter.get("attribution", "")
            pins = inter.get("pins")
            if pins and len(pins) == len(items):
                component.extra["pins"] = pins
            elif pins:
                self.report.warn(
                    f"hotgraphic '{inter['label']}' has {len(pins)} photos but "
                    f"{len(items)} hotspots - pins left as placeholders"
                )
        self._add_component(component)

    def _flush_callout(self, inter: dict) -> None:
        body = paragraphs_to_html(inter["lead_chunks"])
        for item in inter["items"]:
            body += paragraphs_to_html(item.chunks)
        title = inter.get("callout_title", "")
        if not body and not title:
            self.report.warn(
                "a 'Interactivity: Callout' label produced no callout content on "
                f"page '{self.page.title if self.page else '?'}' - the copy under "
                "it is not styled Interactivity-Heading-2 / -body / -Bullet-1"
            )
            return

        icon = config.DEFAULT_HINT_ICON
        upper = title.upper()
        for needle, cls in config.HINT_ICONS.items():
            if needle.upper() in upper:
                icon = cls
                break
        else:
            if title:
                self.report.note(
                    f"callout '{title}' matched no ZOOM IN / QUICK FACT icon; "
                    f"defaulted to {config.DEFAULT_HINT_ICON}"
                )

        callout = Callout(
            title=title,
            body=body,
            icon_class=icon,
            terms=inter["terms"],
            figure=inter.get("figure"),
        )
        self.report.count("callouts")

        # A callout annotates the content it follows. Attach it to the most
        # recent component in this block; if there is none yet, hold it for the
        # next component to be created. A component carries one callout, so a
        # second in a row gets a blank component of its own to sit on.
        self._flush_text()
        block = self.block
        if block and block.components and block.components[-1].hint is None:
            block.components[-1].hint = callout
        elif block and block.components:
            self._host_callout(callout)
        else:
            if self.pending_callout is not None:
                self._host_callout(self.pending_callout)
                self.pending_callout = None
            self.pending_callout = callout

    def _host_callout(self, callout: Callout) -> None:
        """Give a callout a blank component of its own in the current block."""
        host = Component(kind="blank", title="", classes="callout-host")
        host.hint = callout
        self._ensure_block().components.append(host)

    def _settle_pending_callout(self) -> None:
        """A callout still waiting at a page break belongs to the page it was on."""
        if self.pending_callout is not None and self.page is not None:
            callout, self.pending_callout = self.pending_callout, None
            self._host_callout(callout)

    def _flush_all(self) -> None:
        self._flush_interactivity()
        self._flush_text()

    def _flush_references(self) -> None:
        """Turn the collected reference entries into the References page body."""
        if self.mode != "references" or not self.sb.references:
            return
        entries = "".join(f"<li>{ref}</li>" for ref in self.sb.references)
        self._ensure_article()
        self._add_component(
            Component(kind="text", title="References", body=f"<ol>{entries}</ol>")
        )
        self.report.count("references", len(self.sb.references))

    def _flush_questions(self) -> None:
        if not self.questions or self.cyp_article is None:
            return
        article = self.cyp_article
        self._crosscheck_answers(article)
        for n, question in enumerate(self.questions, start=1):
            block = Block(title=f"Question {n}", display_title=f"Question {n}")
            block.components.append(
                Component(
                    kind=question.kind,
                    title=f"Question {n}",
                    body=question.body,
                    question=question,
                    terms=question.terms,
                )
            )
            article.blocks.append(block)
        results = Block(title="Results", display_title="")
        results.components.append(
            Component(
                kind="assessmentResults",
                title="Results",
                extra={"_assessmentId": article.assessment_id},
            )
        )
        article.blocks.append(results)
        self.report.count("questions", len(self.questions))
        self.questions = []
        self.cyp_article = None

    def _crosscheck_answers(self, article: Article) -> None:
        """Compare the Answers key against the storyboard's emboldened options.

        The two are authored independently, so a disagreement means one of them
        is wrong - exactly the thing a programming QC pass needs flagged.
        """
        for n, question in enumerate(self.questions, start=1):
            if question.kind == "matching":
                continue
            keyed = {i for i, o in enumerate(question.options) if o.correct}
            marked = {i for i, o in enumerate(question.options) if o.marked}
            if not marked:
                continue
            if keyed != marked:
                self.report.warn(
                    f"{article.assessment_id} question {n}: the Answers key says "
                    f"{_letters(keyed) or 'nothing'} but the storyboard bolds "
                    f"{_letters(marked)} - verify which is correct"
                )

    def parse(self) -> Storyboard:
        for item in self.body:
            if isinstance(item, Table):
                self._handle_table(item)
            else:
                self._handle_paragraph(item)

        self._flush_all()
        self._flush_references()
        self._flush_questions()
        self._finalise()
        return self.sb

    def _finalise(self) -> None:
        self._apply_side_by_side()
        for page in self.sb.pages:
            page.articles = [a for a in page.articles if not a.is_empty()]
            for article in page.articles:
                article.blocks = [b for b in article.blocks if not b.is_empty()]
        # Cover art and logos sit above the first Heading 1 and are not course
        # content; report what was dropped rather than publishing a stray page.
        for page in self.sb.pages:
            if page.implicit and page.articles:
                dropped = sum(
                    len(b.components) for a in page.articles for b in a.blocks
                )
                self.report.note(
                    f"{dropped} item(s) before the first Heading 1 (cover art / "
                    "logo) were not added to the course"
                )
        self.sb.pages = [p for p in self.sb.pages if p.articles and not p.implicit]

        for page in self.sb.pages:
            seen: set[str] = set()
            for article in page.articles:
                key = article.title.lower()
                if key in seen:
                    self.report.warn(
                        f"page '{page.title}' has two articles titled "
                        f"'{article.title}' - check the storyboard headings"
                    )
                seen.add(key)
        self.sb.figures = [
            Figure(
                index=r.order,
                part_name=r.media,
                ext=Path(r.filename).suffix,
                caption=r.title,
                label=Path(r.filename).stem,
            )
            for r in self.images
        ]
        if self.renderer.programming_notes:
            # De-duplicated: Word repeats the same note across revisions. Notes
            # this build carried out are not listed as still to do.
            seen: dict[str, None] = {}
            for note in self.renderer.programming_notes:
                if note in self.notes_done or (
                    self.how_to_built and config.TITLE_HOW_TO_USE in note.lower()
                ):
                    continue
                seen.setdefault(note, None)
            self.report.programming_notes = list(seen)
            self.report.count("programming notes", len(seen))

        self.report.scripts = self.sb.scripts

        if self.renderer.unmatched_terms:
            self.report.warn(
                f"{len(self.renderer.unmatched_terms)} inline glossary term(s) "
                "have no definition in the glossary table and were built as plain "
                "text: " + ", ".join(sorted(self.renderer.unmatched_terms)[:12])
            )

    def _apply_side_by_side(self) -> None:
        """Carry out "display ... side by side" programming notes.

        The pictures and the copy they pair with sit next to the note - after
        it ("Display image side by side with paragraph below", note first) or
        before it (list and pictures first, note last). The component that
        comes first takes the left column. Several pictures become one stacked
        picture, since a block has only two columns.
        """
        # Latest first, so earlier indexes in the same block stay valid.
        for block, index, note in reversed(self.side_by_side):
            comps = block.components
            after = 0
            while index + after < len(comps) and comps[index + after].kind == "graphic":
                after += 1
            before = 0
            while index - before - 1 >= 0 and comps[index - before - 1].kind == "graphic":
                before += 1

            if after and index + after < len(comps) and comps[index + after].kind == "text":
                pictures = comps[index:index + after]
                text = comps[index + after]
                picture_first = True
            elif before and index - before - 1 >= 0 and comps[index - before - 1].kind == "text":
                pictures = comps[index - before:index]
                text = comps[index - before - 1]
                picture_first = False
            else:
                self.report.warn(
                    f"programming note '{note}' asks for a side-by-side layout, but "
                    "no picture and copy were found next to it - lay it out by hand"
                )
                continue

            picture = pictures[0]
            stacked = self._stack_pictures(pictures) if len(pictures) > 1 else None
            if stacked is not None:
                at = comps.index(pictures[0])
                for extra in pictures:
                    comps.remove(extra)
                comps.insert(at, stacked)
                picture = stacked
            elif len(pictures) > 1:
                self.report.warn(
                    f"programming note '{note}': {len(pictures)} pictures could not "
                    "be stacked - only the first sits beside the copy"
                )

            if "list" in note.lower() and "<ul>" in text.body and not text.body.startswith("<ul>"):
                # "...bulleted list side by side": the paragraphs leading into
                # the list stay full width above the pair.
                cut = text.body.index("<ul>")
                intro = Component(kind="text", title="", body=text.body[:cut],
                                  terms=list(text.terms), hint=text.hint)
                text.hint = None
                text.body = text.body[cut:]
                comps.insert(comps.index(text), intro)

            picture.layout, text.layout = ("left", "right") if picture_first else ("right", "left")
            self.notes_done.add(note)
            self.report.note(
                f"side by side per programming note: "
                f"{'picture | copy' if picture_first else 'copy | picture'}"
                + (f" ({len(pictures)} pictures stacked)" if len(pictures) > 1 else "")
            )

    def _stack_pictures(self, pictures: list[Component]) -> Component | None:
        """One picture made of several, stacked top to bottom."""
        blobs = [p.extra.get("data") for p in pictures]
        if not all(blobs):
            return None
        try:
            data = compose_stack(blobs)
        except (ImportError, OSError) as exc:
            self.report.warn(f"pictures could not be stacked ({exc}) - only the first is shown")
            return None
        first = pictures[0].extra["src"].rsplit("/", 1)[-1]
        name = f"{Path(first).stem}-stack.jpg"
        self.sb.generated_images[name] = data
        stacked = Component(kind="graphic", title=pictures[0].title)
        stacked.extra.update(
            src=f"{config.FIGURE_SRC_PREFIX}/{name}",
            alt=" / ".join(a for a in (p.extra.get("alt", "") for p in pictures) if a),
            attribution=" ".join(p.extra.get("attribution", "") for p in pictures).strip(),
            data=data,
        )
        return stacked

    # ------------------------------------------------------------------

    def _handle_caption(self, html: str) -> None:
        """Route a caption to whatever it labels.

        "Figure 1-3: ..." and "Table 1-1: ..." share one Word style, and a
        table's caption sits *above* it while a figure's sits below. So a
        caption that names a table is held for the next table, one that names a
        figure attaches to the graphic just emitted, and anything else is
        ordinary copy.
        """
        if not html:
            return

        block = self.block
        if block and block.components and block.components[-1].kind == "graphic":
            # A caption with no image of its own annotates the graphic above it.
            graphic = block.components[-1]
            existing = graphic.extra.get("attribution", "")
            graphic.extra["attribution"] = (
                f"{existing} {html}".strip() if existing else html
            )
            return

        # Otherwise it is ordinary copy - and if it names a table, it may also
        # be the caption of a table that follows. It is written into the copy
        # either way and only lifted back out once that table actually arrives,
        # so a "Table 3-1: ..." label above a *picture* of a table is not lost.
        self.text_chunks.append(("p", html))
        kind = tables.RE_CAPTION_KIND.match(tables._plain(html))
        self.pending_caption = html if kind and kind.group(1).lower() == "table" else ""

    # ------------------------------------------------------------------

    def _handle_table(self, table: Table) -> None:
        """Turn a storyboard table into whatever kind of content it is."""
        if self.mode == "skip":
            return
        if self.mode == "glossary":
            self._build_glossary_component(table)
            return

        boxes = _interactivity_boxes(table)
        if boxes:
            for cell in boxes:
                self._handle_box(cell)
            return

        rows, terms = tables.read_table(table, self.renderer)
        parsed_kind = tables.classify(rows, self.mode)

        caption, self.pending_caption = self.pending_caption, ""
        if caption and self.text_chunks and self.text_chunks[-1] == ("p", caption):
            # The caption really did belong to this table - take it back out of
            # the copy so it heads the table instead of preceding it.
            self.text_chunks.pop()
        else:
            caption = ""

        if not any(any(c.strip() for c in r.cells) for r in rows):
            return

        if self.pending_table_component:
            self.pending_table_component = False
            self._build_table_component(rows, terms, caption)
            return

        if parsed_kind == "narration":
            self._build_narration(rows)
            return
        if parsed_kind == "matching":
            self._build_matching(rows)
            return
        if parsed_kind == "selectchoice":
            self._build_selectchoice(rows)
            return
        self._build_data_table(rows, terms, caption)

    def _build_data_table(self, rows, terms, caption: str) -> None:
        """A table of real content, appended to the copy that introduces it."""
        html = tables.to_html(rows, caption)
        if not html:
            return
        self._flush_interactivity()
        self.text_chunks.append(("raw", html))
        self.text_terms.extend(terms)
        # A data table is the end of the passage that introduced it.
        self._flush_text()
        component = self.block.components[-1] if self.block and self.block.components else None
        if component is not None and component.kind == "text":
            component.classes = (
                f"{component.classes} {config.TABLE_COMPONENT_CLASSES}".strip()
            )
        self.report.count("tables")

    def _build_table_component(self, rows, terms, caption: str) -> None:
        """A table asked for as a component, not as HTML inside body copy."""
        self._flush_all()
        component = Component(
            kind="table",
            title=caption or "Table",
            display_title=caption,
            terms=terms,
        )
        component.extra["rows"] = [
            [
                {"text": cell, "colspan": row.spans[i] if i < len(row.spans) else 1}
                for i, cell in enumerate(row.cells)
            ]
            for row in rows
        ]
        self._add_component(component)
        self.report.count("tables")

    def _in_key_concepts(self) -> bool:
        title = (self.article.title if self.article else "").lower()
        return title.startswith(config.TITLE_KEY_CONCEPTS)

    def _build_key_concepts(self, rows, narration: str, onscreen: str) -> bool:
        """The Key Concepts script as an accordion, one panel per topic."""
        panels = tables.parse_narration_panels(rows)
        if not panels:
            return False

        component = Component(kind="accordion", title="", display_title="")
        component.items = [
            _new_item(title=title) for title, _body in panels
        ]
        for item, (_title, body) in zip(component.items, panels):
            item.body = body
        self._add_component(component)
        self.report.count("key concepts accordions")

        untitled = sum(1 for title, _b in panels if not title)
        if untitled:
            self.report.warn(
                f"Key Concepts on page '{self.page.title if self.page else '?'}': "
                f"{untitled} panel(s) have no heading - the on-screen text has to "
                "open with the topic name for it to title the panel"
            )
        # The avatar video still has to be recorded, so its script is published
        # even though no media component is built for it.
        self.sb.scripts.append(
            {
                "title": f"{self.page.title if self.page else ''} Key Concepts".strip(),
                "page": self.page.title if self.page else "",
                "src": "",
                "narration": narration,
                "onscreen": onscreen,
            }
        )
        return True

    def _build_narration(self, rows) -> None:
        """A Narration / On Screen Text script: a video this build cannot make."""
        self._flush_all()
        narration, onscreen = tables.parse_narration(rows)

        if (
            config.KEY_CONCEPTS_AS_ACCORDION
            and self._in_key_concepts()
            and self._build_key_concepts(rows, narration, onscreen)
        ):
            return

        title = tables.narration_title(rows) or (
            self.block.title if self.block else ""
        ) or (self.article.title if self.article else "Key Concepts")

        slug = slugify(title, max_words=6)
        if slug in GENERIC_NARRATION_SLUGS:
            # "Narration for KCs Presented by Avatar" names no section, and every
            # chapter's script says the same - so the page tells them apart.
            title = "Key Concepts"
            slug = f"{self.page.slug if self.page else 'course'}-key-concepts"
        component = Component(kind="media", title=title, display_title="")
        component.extra["src"] = f"{config.MEDIA_SRC_PREFIX}/{slug}.mp4"
        component.extra["narration"] = narration
        component.extra["onscreen"] = onscreen
        self._add_component(component)

        self.sb.scripts.append(
            {
                "title": title,
                "page": self.page.title if self.page else "",
                "src": component.extra["src"],
                "narration": narration,
                "onscreen": onscreen,
            }
        )
        self.report.count("key concepts videos")

    def _build_matching(self, rows) -> None:
        """A pairing exercise, authored once in CYP and again under Answers."""
        stems, options, answers = tables.parse_matching(rows)

        if self.mode == "answers":
            # The Answers copy of the table fills in the letters for a matching
            # question already collected. Find it by its stems.
            for question in self.questions:
                if question.kind == "matching" and not question.match_reconciled:
                    question.match_reconciled = True
                    if answers:
                        question.match_answers = answers
                    if not question.stems:
                        question.stems = stems
                    if not question.match_options:
                        question.match_options = options
                    # It occupies an answer slot, so the letter keys that follow
                    # still line up with their own questions.
                    if self.answer_index < len(self.questions):
                        self.answer_index = self.questions.index(question) + 1
                    return
            # No unreconciled question left: the key was also written out in
            # prose ("5."), which consumed the slot before the table arrived.
            # The Answers copy of the table is still the authoritative one.
            for question in reversed(self.questions):
                if question.kind == "matching":
                    if answers:
                        question.match_answers = answers
                    if stems:
                        question.stems = stems
                    if options:
                        question.match_options = options
                    return
            self.report.warn(
                "an Answers matching table has no Check Your Progress question "
                "to attach to"
            )
            return

        if not self.questions:
            self.report.warn(
                "a matching table appears before any Check Your Progress "
                "question stem - the table was skipped"
            )
            return

        question = self.questions[-1]
        if question.options:
            # The stem sits directly above its table, so a question that
            # already has options absorbed this one's stem as its last option.
            # Take it back and give the table a question of its own.
            stem = question.options.pop()
            question = Question(body=stem.text)
            self.questions.append(question)
        question.kind = "matching"
        question.stems = stems
        question.match_options = options
        if answers:
            question.match_answers = answers
        self.report.count("matching questions")

    def _build_selectchoice(self, rows) -> None:
        """A grid question: a statement per row, an X in the column that applies.

        The X is the answer key, so these need nothing from the Answers
        section - but they still occupy a slot there, which the answer index
        has to skip over.
        """
        choices, items = tables.parse_selectchoice(rows)
        if not items:
            self.report.warn(
                "a grid table under Check Your Progress had no usable rows"
            )
            return

        if self.mode == "answers":
            for question in self.questions:
                if question.kind == "selectchoice" and not question.match_reconciled:
                    question.match_reconciled = True
                    self.answer_index = self.questions.index(question) + 1
                    return
            return

        question = self.questions[-1] if self.questions else None
        if question is None:
            self.report.warn(
                "a grid table appears before any Check Your Progress question "
                "stem - the table was skipped"
            )
            return
        if question.options:
            # As with a matching table, the stem directly above was absorbed as
            # the previous question's last option. Take it back.
            stem = question.options.pop()
            question = Question(body=stem.text)
            self.questions.append(question)

        question.kind = "selectchoice"
        question.choices = choices
        question.grid_items = items
        self.report.count("grid questions")

    def _build_glossary_component(self, table: Table) -> None:
        rows = []
        for row in table.rows:
            cells = row.cells
            if len(cells) < 2:
                continue
            term = _cell_text(cells[0])
            definition = _cell_text(cells[1])
            if term:
                rows.append(f"<tr><td><strong>{term}</strong></td><td>{definition}</td></tr>")
        body = (
            "<table><thead><tr><th>Term</th><th>Definition</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
        )
        self._add_component(
            Component(
                kind="text",
                title="Glossary",
                body=body,
                classes="glossary vertical-table-data-highlight",
            )
        )
        self.report.count("glossary terms", len(rows))

    # ------------------------------------------------------------------
    # Interactivities drawn as boxes (a table cell per interactivity)
    # ------------------------------------------------------------------

    def _handle_box(self, cell) -> None:
        """Parse one boxed interactivity: its label, then its panels.

        Inside a box the author is free with styles - panel headings arrive as
        Heading 4, as bold Normal, or as plain short lines - but the box itself
        says where the interactivity starts and ends, so none of it can leak
        into the page or be mistaken for a block heading.
        """
        entries = []
        for para in cell.paragraphs:
            style = _style(para)
            rendered = self.renderer.render(para)
            raw = para.text.strip()
            if style in config.STYLE_DROP or (not raw and not rendered.has_image):
                continue
            entries.append((para, style, rendered, raw))
        if not entries:
            return

        para, _style_name, rendered, raw = entries[0]
        self._handle_interactivity_heading(para, rendered, raw)
        if self.interactivity is None:
            return  # an unknown type (reported) or a table label

        rest = entries[1:]
        headings = _box_headings(rest)
        for index, (para, style, rendered, raw) in enumerate(rest):
            if RE_PLACEHOLDER.match(raw):
                self.renderer.programming_notes.append(raw)
            elif RE_BARE_URL.match(raw):
                where = self._box_item_title() or self.interactivity["label"]
                self.renderer.programming_notes.append(f"image source ({where}): {raw}")
            elif index in headings:
                self._box_heading(rendered, raw)
            else:
                self._box_content(rendered, style)
        self._flush_interactivity()

    def _box_item_title(self) -> str:
        inter = self.interactivity
        if inter and inter["items"]:
            return tables._plain(inter["items"][-1].title)
        return ""

    def _box_heading(self, rendered, raw: str) -> None:
        inter = self.interactivity
        title = rendered.html
        if RE_ITEM_PREFIX.match(raw):
            # "Hotspot 1: Pharmacologic treatments" -> "Pharmacologic treatments".
            # A bare "Hotspot 1" leaves nothing, which is right: the pin already
            # carries the number.
            title = clean_html(RE_ITEM_PREFIX.sub(r"\1", _unwrap_bold(title)))
        title = _unwrap_bold(RE_SYMBOL_PREFIX.sub("", title).strip())
        inter["terms"].extend(rendered.terms)

        if inter["kind"] == "callout":
            if not inter["callout_title"]:
                inter["callout_title"] = title
            else:
                inter["lead_chunks"].append(("p", f"<strong>{title}</strong>"))
            return

        inter["items"].append(_new_item(title=title))
        if rendered.has_image:
            self._attach_box_image(rendered.image_rids)

    def _box_content(self, rendered, style: str) -> None:
        inter = self.interactivity
        after_base_image = inter["kind"] == "hotgraphic" and inter.get("base_image_done")
        if rendered.has_image:
            self._attach_box_image(rendered.image_rids)

        html = rendered.html
        # "IMG o": a stray character typed beside a picture is not copy.
        if not html or (rendered.has_image and len(tables._plain(html)) <= 2):
            return

        if inter["kind"] == "hotgraphic" and (
            after_base_image
            or style in config.STYLE_CAPTION
            or style == config.STYLE_INTERACT_LABEL
        ):
            # Below a hot-spot image sit its caption and abbreviation key.
            inter["attribution"] = f"{inter['attribution']} {html}".strip()
            return

        if style in config.STYLE_INTERACT_BULLET or style in config.STYLE_BULLET_L1:
            kind = "li1"
        elif style in config.STYLE_INTERACT_BULLET_L2 or style in config.STYLE_BULLET_L2:
            kind = "li2"
        elif style in config.STYLE_ORDERED:
            kind = "num"
        else:
            kind = "p"
        target = inter["items"][-1].chunks if inter["items"] else inter["lead_chunks"]
        target.append((kind, html))
        inter["terms"].extend(rendered.terms)

    def _attach_box_image(self, rids: list[str]) -> None:
        inter = self.interactivity
        if inter["kind"] != "hotgraphic":
            target = inter["items"][-1] if inter["items"] else None
            if target is not None and target.figure is not None:
                # The panel already has its image; a second one belongs in the
                # copy, at the point the author placed it.
                for rid in rids:
                    src, alt = self._figure_src(rid)
                    if src:
                        target.chunks.append(
                            ("raw", f"<p><img src='{src}' alt='{alt}'></p>")
                        )
                return
            self._attach_interactivity_image(rids)
            return
        # A hot-spot image is the backdrop the pins sit on, wherever in the box
        # the author happened to paste it.
        records = []
        for rid in rids:
            rec = self._resolve_rid(rid)
            if rec is not None and rec.filename not in {r.filename for r in records}:
                records.append(rec)
        if inter["figure"] is None and len(records) > 1:
            # Several photos grouped in one drawing, a hotspot per photo: they
            # become one backdrop, panels side by side, a pin over each.
            self._compose_backdrop(records)
            return
        if inter["figure"] is not None:
            self.report.warn(
                f"hotgraphic '{inter['label']}' on page "
                f"'{self.page.title if self.page else '?'}' has more than one image "
                "- only the first is used"
            )
            return
        rec = records[0] if records else None
        if rec is not None:
            inter["figure"] = Figure(
                index=0, part_name="", ext="", caption=rec.alt or rec.title,
                label="", src=rec.src,
            )
            inter["base_image_done"] = True

    def _compose_backdrop(self, records: list[ImageRecord]) -> None:
        inter = self.interactivity
        where = self.page.title if self.page else "?"
        try:
            data, pins = compose_panels([r.data for r in records])
        except (ImportError, OSError) as exc:
            self.report.warn(
                f"hotgraphic '{inter['label']}' on page '{where}': its "
                f"{len(records)} photos could not be composed into one backdrop "
                f"({exc}) - only the first is used"
            )
            first = records[0]
            inter["figure"] = Figure(
                index=0, part_name="", ext="", caption=first.alt, label="",
                src=first.src,
            )
            inter["base_image_done"] = True
            return
        name = f"{Path(records[0].filename).stem}-composite.jpg"
        self.sb.generated_images[name] = data
        inter["figure"] = Figure(
            index=0, part_name="", ext="", caption=records[0].alt, label="",
            src=f"{config.FIGURE_SRC_PREFIX}/{name}",
        )
        inter["pins"] = pins
        inter["base_image_done"] = True
        self.report.note(
            f"hotgraphic '{inter['label']}' on page '{where}': {len(records)} "
            f"photos composed into {name}, a pin centred over each"
        )

    # ------------------------------------------------------------------

    def _handle_paragraph(self, para: Paragraph) -> None:
        style = _style(para)
        if (
            self.mode == "skip"
            and style not in config.STYLE_PAGE
            and style not in config.STYLE_ARTICLE
        ):
            # Print-only copy is not rendered at all, so its glossary terms
            # and notes are not reported against the course.
            return
        rendered = self.renderer.render(para)
        text = rendered.html
        raw = para.text.strip()

        if RE_PLACEHOLDER.match(raw):
            # "{Animation: ...}" names media still to be made - not copy.
            self.renderer.programming_notes.append(raw.strip())
            return

        if style in config.STYLE_DROP and self.mode != "references":
            # A whole paragraph of medical/legal citations - review only. On
            # the References page the same style marks an entry typed in the
            # wrong style, which is still a reference.
            return

        if style in config.STYLE_PAGE:
            self._start_page(raw)
            return

        if style in config.STYLE_ARTICLE:
            self._start_article(raw)
            return

        if self.mode == "skip":
            # Print-only copy, e.g. "Key Concepts (For Print)".
            return

        if style in config.STYLE_CYP_QUESTIONS:
            style = config.STYLE_CYP_QUESTION

        if (
            style in config.STYLE_PROGRAMMING_NOTE
            and self.mode != "answers"
            and _interactivity_label(raw) is None
            and not raw.lower().startswith(config.INTERACTIVITY_END_PREFIX)
        ):
            # An instruction to the programmer. It goes to the report; a figure
            # sitting in the same paragraph is still a figure.
            if raw:
                self.renderer.programming_notes.append(raw)
            side = config.SIDE_BY_SIDE_PHRASE in raw.lower()
            if rendered.has_image or side:
                self._flush_interactivity()
                self._flush_text()
            if side:
                # Laid out once the block is complete: the images and copy it
                # pairs may sit before the note or after it.
                block = self._ensure_block()
                self.side_by_side.append((block, len(block.components), raw))
            for rid in rendered.image_rids:
                self._add_graphic(rid)
            return

        if self.mode == "answers":
            # `text`, not `raw`: the source citation has been stripped from it,
            # leaving just the key ("D", "B, C", "True").
            self._handle_answer(text)
            return

        if style in config.STYLE_BLOCK:
            self._start_block(raw, style)
            return

        if style in config.STYLE_REFERENCE or self.mode == "references":
            if text:
                # The list is numbered when it renders, so a number typed in
                # front of an entry would be a second one.
                self.sb.references.append(_drop_numbering(text))
            return

        # The label is sometimes typed without the Interactivity-Heading-1
        # style, so match on the text as well.
        if (
            style == config.STYLE_INTERACT_H1
            or _interactivity_label(raw) is not None
            or raw.lower().startswith(config.INTERACTIVITY_END_PREFIX)
        ):
            self._handle_interactivity_heading(para, rendered, raw)
            return

        if style == config.STYLE_CYP_QUESTION:
            # Some storyboards style a question's options CYP-Question as well
            # as its stem. A real stem is never immediately followed by another
            # stem, so a CYP-Question paragraph that follows one and does not
            # read as a stem is an option of the question already open.
            if (
                self.last_cyp_style == config.STYLE_CYP_QUESTION
                and self.questions
                and not _looks_like_question(raw)
            ):
                self._handle_option(text)
            else:
                self._handle_question(text, raw)
            self.last_cyp_style = style
            return

        if style in config.STYLE_CYP_ANSWER:
            self.last_cyp_style = style
            self._handle_option(text)
            return

        if self.mode == "cyp":
            # Inside Check Your Progress, plain paragraphs are answer options -
            # unless they read as a question stem, which happens when an author
            # forgets to apply the CYP-Question style. Either way this ends the
            # run of CYP-Question paragraphs, so the next stem is recognised as
            # one even where the options above it were not styled as answers.
            if not text:
                return
            if _looks_like_question(raw) or not self.questions:
                self._handle_question(text, raw)
                self.last_cyp_style = config.STYLE_CYP_QUESTION
            else:
                self._handle_option(text)
                self.last_cyp_style = "option"
            return

        if self.interactivity is not None:
            if self._handle_interactivity_content(para, rendered, style, raw):
                return
            self._flush_interactivity()

        self._handle_body(para, rendered, style)

    # ------------------------------------------------------------------
    # Structure starts
    # ------------------------------------------------------------------

    def _start_page(self, title: str) -> None:
        if (
            title.lower() in (config.TITLE_CHECK_YOUR_PROGRESS, config.TITLE_ANSWERS)
            and self.page is not None
            and self.page.is_chapter
        ):
            # Some storyboards promote a chapter's Check Your Progress and its
            # Answers to Heading 1. They still belong to the chapter above -
            # the assessment is that chapter's, and Answers is its key.
            self._start_article(title)
            return

        self._flush_all()
        self._settle_pending_callout()
        self.last_cyp_style = ""
        self._flush_references()
        self._flush_questions()

        lower = title.lower()
        self.mode = "body"
        if lower == config.TITLE_GLOSSARY:
            self.mode = "glossary"
        elif lower == config.TITLE_REFERENCES:
            self.mode = "references"

        display = title
        short = title.split(":")[0].strip()
        is_chapter = lower.startswith(config.CHAPTER_TITLE_PREFIX)

        self.page = Page(
            slug=slugify(short),
            title=short if is_chapter else title,
            display_title=display,
            is_chapter=is_chapter,
        )
        self.sb.pages.append(self.page)
        self.article = None
        self.block = None
        self.report.count("pages")

        if config.HOW_TO_USE_TEMPLATE and lower == config.TITLE_HOW_TO_USE:
            self._build_how_to()

    def _build_how_to(self) -> None:
        """The "How to Use This Module" page, as the Figma template draws it.

        The storyboard's version of this page is print copy (its own
        programming note says so); the course shows the same four rows in
        every module - a line of help beside its player icon.
        """
        page = self.page
        assert page is not None
        for n, (body, icon) in enumerate(config.HOW_TO_USE_ROWS, start=1):
            article = Article(title=f"{page.title} {n}", display_title="")
            block = Block()
            article.blocks.append(block)
            page.articles.append(article)
            block.components.append(Component(
                kind="text", title="", body=body,
                classes=config.HOW_TO_USE_TEXT_CLASSES, layout="left",
            ))
            icon_component = Component(
                kind="graphic", title="", classes=config.HOW_TO_USE_ICON_CLASSES,
                layout="right",
            )
            icon_component.extra.update(src=icon, alt="", expand=False)
            block.components.append(icon_component)
        self.how_to_built = True
        # The storyboard's own copy for this page is not built.
        self.mode = "skip"
        self.report.note(
            "'How to Use This Module' built from the Figma template "
            "(config.HOW_TO_USE_ROWS); the storyboard's print copy was not used"
        )

    def _start_article(self, title: str) -> None:
        self._flush_all()
        self.last_cyp_style = ""
        page = self._ensure_page()
        lower = title.lower()

        if lower == config.TITLE_ANSWERS:
            # Not an article: an answer key for the questions just collected.
            self.mode = "answers"
            self.answer_index = 0
            self.article = None
            self.block = None
            return

        self._flush_questions()

        if lower.endswith(config.TITLE_PRINT_ONLY):
            # Authored for the print PDF only; the course has its own version.
            self.mode = "skip"
            self.article = None
            self.block = None
            self.report.note(f"'{title}' on page '{page.title}' is print-only - not built")
            return
        for suffix in config.TITLE_PROGRAMMING_SUFFIX:
            if lower.endswith(suffix):
                title = title[: -len(suffix)].strip()
                lower = title.lower()

        if lower == config.TITLE_CHECK_YOUR_PROGRESS:
            self.assessment_count += 1
            self.article = Article(
                title=title,
                display_title=title,
                is_assessment=True,
                assessment_id=f"Assessment {self.assessment_count}",
                score_to_pass=config.ASSESSMENT_SCORE_TO_PASS,
                page_level_progress=False,
            )
            self.mode = "cyp"
            self.questions = []
            self.cyp_article = self.article
        else:
            self.mode = "glossary" if page.slug == "glossary" else "body"
            if page.slug == "references":
                self.mode = "references"
            display = "" if lower == config.TITLE_LEARNING_OBJECTIVES else title
            self.article = Article(
                title=title,
                display_title=display,
                page_level_progress=title.lower().startswith("section"),
            )

        page.articles.append(self.article)
        self.block = None
        self.report.count("articles")

    def _start_block(self, title: str, style: str) -> None:
        self._flush_all()
        self._ensure_article()
        level = _heading_level(style)
        block = self.block
        if (
            block is not None
            and block.title
            and not block.components
            and not self.pending_subheading
            and level > self.block_level
        ):
            # "PROPEL 2 Results" (Heading 3) straight followed by "Baseline
            # Demographics" (Heading 4): the outer heading has no copy of its
            # own, so it titles the block and the inner one leads its copy.
            self.pending_subheading = title
            self.report.count("sub-headings kept inside their parent block")
            return
        self.pending_subheading = ""
        self.block_level = level
        self.block = Block(title=title, display_title=title)
        self.article.blocks.append(self.block)  # type: ignore[union-attr]
        self.report.count("blocks")

    # ------------------------------------------------------------------
    # Body copy
    # ------------------------------------------------------------------

    def _handle_body(self, para: Paragraph, rendered, style: str) -> None:
        kind = _list_kind(para, style)
        if kind is None and self.deferred_graphics:
            # The list those pictures were pasted into has ended.
            self._flush_text()

        icon = ""
        if rendered.has_image:
            if kind is not None:
                # A picture pasted into a list item. A small one is the item's
                # bullet icon, as the authored course draws it; a photo
                # ("{IMG}Psychologists") goes after the list, keeping it whole.
                for rid in rendered.image_rids:
                    rec = self._resolve_rid(rid)
                    if rec is None or not rec.src:
                        continue
                    if not icon and _is_icon(rec):
                        icon = f"<img class='{config.LIST_ICON_CLASS}' src='{rec.src}' alt=''> "
                    else:
                        self.deferred_graphics.append(rec)
            else:
                self._flush_text()
                for rid in rendered.image_rids:
                    self._add_graphic(rid)

        if not rendered.html:
            return
        if icon:
            rendered.html = f"{icon}<div>{rendered.html}</div>"

        if kind is None:
            if style in config.STYLE_CAPTION:
                return self._handle_caption(rendered.html)
            kind = "p"

        self.text_chunks.append((kind, rendered.html))
        self.text_terms.extend(rendered.terms)
        self.pending_caption = ""

    def _add_graphic(self, rid: str) -> None:
        rec = self._resolve_rid(rid)
        if rec is not None:
            self._add_graphic_record(rec)

    def _add_graphic_record(self, rec: ImageRecord) -> None:
        if not rec.src:
            return
        src, alt = rec.src, (rec.alt or rec.title)
        component = Component(kind="graphic", title=alt[:80], figure=None)
        component.extra["src"] = src
        component.extra["alt"] = alt
        # Kept for layouts that combine pictures (see _apply_side_by_side).
        component.extra["data"] = rec.data
        self._add_component(component)
        self.report.count("figures")

    # ------------------------------------------------------------------
    # Interactivities
    # ------------------------------------------------------------------

    def _handle_interactivity_heading(self, para: Paragraph, rendered, raw: str) -> None:
        lower = raw.lower()

        # "End Interactivity: Accordions" closes the open one; without this the
        # label itself leaks into the course as body copy.
        if lower.startswith(config.INTERACTIVITY_END_PREFIX):
            self._flush_interactivity()
            return

        label_parts = _interactivity_label(raw)
        if label_parts is not None:
            key, heading = label_parts
            self._flush_interactivity()
            # Body copy above the interactivity is its own component, and it is
            # also what a callout attaches itself to.
            self._flush_text()
            kind = config.INTERACTIVITY_MAP.get(key)
            if kind is None:
                self.report.warn(f"unknown interactivity type '{key}' - skipped")
                return
            label = heading or key.title()
            self.interactivity = {
                "kind": kind,
                "label": label,
                "items": [],
                "lead_chunks": [],
                "terms": [],
                "tab_layout": "vertical"
                if key in config.VERTICAL_TAB_LABELS
                else "horizontal",
                "figure": None,
                "attribution": "",
                "callout_title": "",
                #: True once copy left styled Normal has been claimed by this
                #: interactivity, so the rest of that run is claimed too.
                "loose": False,
            }
            if kind == "table":
                # A table has no panels; the label simply says that the table
                # below is a component in its own right rather than HTML in the
                # copy. Nothing is left open for content to accumulate into.
                self.interactivity = None
                self.pending_table_component = True
                self.report.count("interactivity: table")
                return

            self.report.count(f"interactivity: {kind}")
            return

        # An Interactivity-Heading-1 that is not a label is the interactivity's
        # own graphic (hot-spot base image) or stray copy.
        if self.interactivity is not None and rendered.has_image:
            self._attach_interactivity_image(rendered.image_rids)
            return
        self._handle_body(para, rendered, "Normal")

    def _attach_interactivity_image(self, rids: list[str]) -> None:
        """Bind an image to the open item, or to the interactivity's own graphic.

        A drawing before any item has started is the base image (the hot-spot
        backdrop); afterwards it illustrates the item it sits inside.
        """
        inter = self.interactivity
        if inter is None:
            return
        src, alt = self._figure_src(rids[0])
        if not src:
            return
        figure = Figure(index=0, part_name="", ext="", caption=alt, label="", src=src)
        if inter["items"]:
            item = inter["items"][-1]
            if inter["kind"] == "accordion" and item.chunks:
                # A figure partway through a panel's copy stays where the
                # author put it - above its caption - rather than being lifted
                # out as the panel's image.
                item.chunks.append(("raw", f"<p><img src='{src}' alt='{alt}'></p>"))
                return
            item.figure = figure
        else:
            inter["figure"] = figure

    def _handle_interactivity_content(
        self, para: Paragraph, rendered, style: str, raw: str
    ) -> bool:
        """Return True if the paragraph belonged to the open interactivity."""
        inter = self.interactivity
        assert inter is not None

        match = RE_ITEM_PREFIX.match(raw)
        is_item_heading = style == config.STYLE_INTERACT_H2 or match is not None

        if is_item_heading:
            title = rendered.html
            if match:
                # Re-render so the "Accordion 1:" prefix does not leak into the
                # title, keeping any inline markup in the remainder.
                title = clean_html(RE_ITEM_PREFIX.sub(r"\1", title))
            title = RE_SYMBOL_PREFIX.sub("", title).strip()

            if inter["kind"] == "callout":
                inter["callout_title"] = title
                inter["terms"].extend(rendered.terms)
                # Callout headings often carry their own icon.
                if rendered.has_image:
                    self._attach_interactivity_image(rendered.image_rids)
                return True

            if (
                match is None
                and not inter["items"]
                and inter["kind"] not in QUESTION_INTERACTIVITIES
            ):
                # A lead-in such as "Upon completion of this chapter...".
                # It heads the single panel rather than naming it.
                inter["items"].append(
                    _new_item(title=self.article.title if self.article else "")
                )
                inter["items"][-1].chunks.append(("p", f"<strong>{title}</strong>"))
            else:
                inter["items"].append(_new_item(title=title))
            inter["terms"].extend(rendered.terms)
            return True

        if style == config.STYLE_INTERACT_LABEL:
            if rendered.html:
                inter["attribution"] = rendered.html
            return True

        if rendered.has_image:
            self._attach_interactivity_image(rendered.image_rids)
            if not rendered.html:
                return True

        if style in config.STYLE_INTERACT_BULLET or style in config.STYLE_BULLET_L1:
            kind = "li1"
        elif style in config.STYLE_INTERACT_BULLET_L2 or style in config.STYLE_BULLET_L2:
            kind = "li2"
        elif style in config.STYLE_ORDERED:
            kind = "num"
        elif style == config.STYLE_INTERACT_BODY:
            kind = "p"
        elif style in config.STYLE_BODY and (
            inter["loose"] or (not inter["items"] and not inter["lead_chunks"])
        ):
            # An interactivity whose content was left styled Normal. The first
            # such paragraph can only belong to the label above it, and once one
            # has been claimed the rest of the run belongs to it too - otherwise
            # a callout would keep its heading and spill its body into the page.
            # The run ends at the next heading, which closes the interactivity.
            if not inter["loose"]:
                inter["loose"] = True
                if inter["kind"] == "callout" and not inter["callout_title"]:
                    # An untitled callout's first line is its heading.
                    # Callout titles are plain text; the heading's own bold is
                    # styling, not copy.
                    inter["callout_title"] = tables._plain(rendered.html)
                    inter["terms"].extend(rendered.terms)
                    return True
            kind = "p"
        else:
            return False  # not ours - caller closes the interactivity

        if rendered.html:
            target = (
                inter["items"][-1].chunks if inter["items"] else inter["lead_chunks"]
            )
            target.append((kind, rendered.html))
            inter["terms"].extend(rendered.terms)
        return True

    # ------------------------------------------------------------------
    # Check Your Progress
    # ------------------------------------------------------------------

    def _handle_question(self, text: str, raw: str) -> None:
        if self.mode == "answers":
            self._handle_answer(text)
            return
        if not text:
            return
        self.questions.append(
            Question(
                body=_drop_numbering(text),
                select_all=bool(RE_SELECT_ALL.search(raw)),
            )
        )

    def _handle_option(self, text: str) -> None:
        if not text or not self.questions:
            return
        clean, marked = _strip_answer_marker(text)
        self.questions[-1].options.append(Option(text=clean, marked=marked))

    def _handle_answer(self, raw: str) -> None:
        # Defensive: catch a citation that was typed without its character style.
        raw = re.sub(r"\[[^\]]*\]", "", raw).strip()
        # A superscript reference marker is decoration on the key, not part of it.
        raw = RE_SUP.sub("", raw).strip()
        # "4.\tB" - the question number the author typed in front of the key.
        raw = _drop_numbering(raw)
        if not raw:
            # Blank paragraphs are frequent in the Answers section and mean
            # nothing; consuming a slot for one would offset every key below.
            return

        match = RE_ANSWER_KEY.match(raw)
        if not match:
            nxt = (
                self.questions[self.answer_index]
                if self.answer_index < len(self.questions)
                else None
            )
            if nxt is not None and nxt.kind in ("selectchoice", "matching"):
                # A grid or matching question's key is written out in prose.
                nxt.match_reconciled = True
                self.answer_index += 1
                return
            if raw:
                self.report.warn(f"unrecognised answer key '{raw}' - ignored")
            return
        if self.answer_index >= len(self.questions):
            self.report.warn(f"answer key '{raw}' has no matching question")
            return

        question = self.questions[self.answer_index]
        self.answer_index += 1
        if question.kind in ("selectchoice", "matching"):
            # Answered by its own table; the Answers section restates the key
            # as prose, which is for a human reviewer rather than for us.
            question.match_reconciled = True
            return

        if match.group(1):  # True / False
            wanted = match.group(1).lower()
            for option in question.options:
                if option.text.strip().lower() == wanted:
                    option.correct = True
                    break
            else:
                self.report.warn(
                    f"answer '{raw}' did not match any option of question "
                    f"{self.answer_index}"
                )
            return

        letters = re.findall(r"[A-H]", match.group(2).upper())
        if (
            len(letters) > 1
            and RE_ORDERING.search(question.body)
            and len(set(letters)) == len(letters) == len(question.options)
            and len(letters) <= len(ORDINALS)
        ):
            _make_ordering(question, letters)
            self.report.count("ordering questions")
            return
        for letter in letters:
            idx = ord(letter) - ord("A")
            if idx < len(question.options):
                question.options[idx].correct = True
            else:
                self.report.warn(
                    f"answer '{letter}' is out of range for question "
                    f"{self.answer_index} ({len(question.options)} options)"
                )
        if len(letters) > 1:
            question.select_all = True


RE_WHOLLY_BOLD = re.compile(r"^\s*<strong>(.*)</strong>\s*$", re.S)


def _make_ordering(question: Question, letters: list[str]) -> None:
    """Turn "put these in order" into a matching question.

    Each option becomes a row, and each row's dropdown offers the positions
    First, Second, ... The key "C, B, A" says C comes first, so First matches
    C's row. No ordering component ships in base/Source; matching expresses
    the same exercise with an unambiguous answer key.
    """
    positions = list(ORDINALS[: len(letters)])
    question.kind = "matching"
    question.stems = [
        (chr(ord("A") + i), option.text) for i, option in enumerate(question.options)
    ]
    question.match_options = positions
    question.match_answers = dict(zip(letters, positions))
    question.match_reconciled = True
    question.options = []
    question.select_all = False


def _unwrap_bold(html: str) -> str:
    """"<strong>Title</strong>" -> "Title": a heading's bold is styling."""
    match = RE_WHOLLY_BOLD.match(html)
    if match and "<strong>" not in match.group(1):
        return match.group(1).strip()
    return html


def _heading_level(style: str) -> int:
    """3 for "Heading 3" and so on; 0 when the style carries no number."""
    match = re.search(r"(\d+)\s*$", style)
    return int(match.group(1)) if match else 0


def _is_icon(rec: ImageRecord) -> bool:
    """A picture small enough to be a list bullet rather than a figure."""
    try:
        import io
        from PIL import Image

        with Image.open(io.BytesIO(rec.data)) as image:
            return max(image.size) <= config.LIST_ICON_MAX_PX
    except Exception:  # no Pillow, or not a bitmap Pillow can read
        return False


def _list_kind(para: Paragraph, style: str) -> str | None:
    """``li1`` / ``li2`` / ``num`` for a list paragraph, else None.

    Word's own "List Paragraph" style is a list item only when the paragraph
    carries numbering - the same style is used for loose paragraphs too.
    """
    if style in config.STYLE_BULLET_L1:
        return "li1"
    if style in config.STYLE_BULLET_L2:
        return "li2"
    if style in config.STYLE_ORDERED:
        return "num"
    if style == "List Paragraph":
        ppr = para._p.pPr
        if ppr is not None and ppr.numPr is not None:
            return "li1"
    return None


def _cell_text(cell) -> str:
    """A glossary cell's text without its citation runs.

    ``cell.text`` would keep "[Taber's_Arthralgia]"-style sources, which are
    styled as citations but match no loose-citation pattern.
    """
    parts = []
    for para in cell.paragraphs:
        parts.append("".join(
            run.text for run in para.runs
            if (run.style.name if run.style is not None else "") not in config.CHAR_CITATION
        ))
    return clean_html(" ".join(p.strip() for p in parts if p.strip()))


def _unique_cells(table: Table) -> list:
    """Each cell once, in reading order - merged cells repeat in python-docx."""
    seen: set[int] = set()
    cells = []
    for row in table.rows:
        for cell in row.cells:
            if id(cell._tc) not in seen:
                seen.add(id(cell._tc))
                cells.append(cell)
    return cells


def _first_text(cell) -> str:
    for para in cell.paragraphs:
        if para.text.strip():
            return para.text.strip()
    return ""


MAX_BOX_HEADING = 120
SHORT_HEADING_WORDS = 6


def _box_headings(entries: list) -> set[int]:
    """Which paragraphs of a box are panel headings, by the box's own habit.

    Tried in order, and the first that finds any wins: heading-styled lines
    (Heading 4, Interactivity-Heading-2), then wholly bold lines, then - for a
    box authored entirely in plain Normal - short lines with no closing
    punctuation. A heading style on a whole sentence is a slip, not a heading.
    """
    def fits(raw: str) -> bool:
        return bool(raw) and len(raw) <= MAX_BOX_HEADING and not raw.endswith((".", ",", ";"))

    lists = config.STYLE_BULLET_L1 | config.STYLE_BULLET_L2 | config.STYLE_INTERACT_BULLET
    explicit = {
        i
        for i, (_p, style, _r, raw) in enumerate(entries)
        if (style in config.STYLE_BLOCK or style == config.STYLE_INTERACT_H2) and fits(raw)
    }
    if explicit:
        return explicit
    bold = {
        i
        for i, (_p, style, rendered, raw) in enumerate(entries)
        if style not in lists
        and fits(raw)
        and not raw.endswith(":")
        and _unwrap_bold(rendered.html) != rendered.html
    }
    if bold:
        return bold
    return {
        i
        for i, (_p, style, rendered, raw) in enumerate(entries)
        if style in config.STYLE_BODY
        and not rendered.has_image
        and fits(raw)
        and not raw.endswith(":")
        and len(raw.split()) <= SHORT_HEADING_WORDS
    }


def _interactivity_boxes(table: Table) -> list:
    """The cells of a table used as boxes around interactivities, if it is one.

    Some storyboards draw each interactivity in a 1x1 table - or stack two in
    one table, a row each - with its label as the first line. Such a table is
    not data: every non-empty cell has to open with a label for it to count.
    """
    cells = [c for c in _unique_cells(table) if _first_text(c)]
    if not cells:
        return []
    for cell in cells:
        if _interactivity_label(_first_text(cell)) is None:
            return []
    return cells


def _letters(indexes: set[int]) -> str:
    return ", ".join(chr(ord("A") + i) for i in sorted(indexes))


def _strip_answer_marker(text: str) -> tuple[str, bool]:
    """Split an option into its copy and whether it was flagged as correct.

    Only a wholly emboldened option counts as a marker; bold *within* an option
    is ordinary emphasis and is left alone.
    """
    match = RE_WHOLLY_BOLD.match(text)
    if not match or "<strong>" in match.group(1):
        return text, False
    return match.group(1).strip(), True


RE_SCALE = re.compile(r"scale\s*:?\s*(-?\d+)\s*(?:to|-|–)\s*(-?\d+)", re.I)
RE_ANSWER = re.compile(r"answer\s*:?\s*(-?\d+)\s*$", re.I)
RE_RANGE = re.compile(r"range\s*:?\s*(-?\d+)\s*(?:to|-|–)\s*(-?\d+)", re.I)
RE_LABELS = re.compile(r"labels?\s*:?\s*(.+?)\s*(?:,|/|–|-)\s*(.+)$", re.I)


def _slider_settings(items: list[Item], report: Report) -> dict:
    """Read a slider's scale and answer out of its panel headings.

    The storyboard states them in plain words - "Scale: 1 to 10",
    "Answer: 7", "Range: 4 to 9", "Labels: low, high" - because a slider has
    no natural list of panels to carry them.
    """
    settings: dict = {}
    for item in items:
        text = re.sub(r"<[^>]+>", "", item.title).strip()
        if match := RE_SCALE.search(text):
            settings["scaleStart"] = int(match.group(1))
            settings["scaleEnd"] = int(match.group(2))
        elif match := RE_RANGE.search(text):
            settings["correctBottom"] = int(match.group(1))
            settings["correctTop"] = int(match.group(2))
        elif match := RE_ANSWER.search(text):
            settings["correctAnswer"] = int(match.group(1))
        elif match := RE_LABELS.match(text):
            settings["labelStart"] = match.group(1).strip()
            settings["labelEnd"] = match.group(2).strip()
        elif text:
            report.note(f"slider setting '{text}' was not recognised")
    return settings


def _new_item(title: str = "") -> Item:
    return Item(title=title, tab_title=title)


def parse_storyboard(
    path: Path, report: Report, originals: Path | None = None
) -> Storyboard:
    """Parse ``path``. ``originals`` holds the course's delivered hi-res images."""
    return StoryboardParser(path, report, originals).parse()
