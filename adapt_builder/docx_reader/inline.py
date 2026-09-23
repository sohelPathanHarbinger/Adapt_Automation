"""Word runs -> Adapt-flavoured inline HTML.

Three conventions in this storyboard drive everything here:

* runs styled ``Glossary item Char`` are glossary terms and become
  ``<span class="notify g-term" id='...'>`` plus a ``_notifyAnywhere`` entry;
* runs styled ``Refrence text Char`` are medical/legal source citations
  (``[Attruby PI p2/A]``) that exist for review only and never ship - though
  only their bracket groups are citations: copy the style was painted over by
  mistake is kept (see ``_uncite``);
* bold / italic / superscript map to ``<strong>`` / ``<em>`` / ``<sup>``.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

from docx.text.hyperlink import Hyperlink
from docx.text.paragraph import Paragraph
from docx.text.run import Run

from .. import config
from ..model import GlossaryTerm

#: Citations that escaped the character style, e.g. a caption typed by hand.
#: Deliberately narrow: it only fires on bracket groups that look like a source
#: reference, so genuine content brackets such as "[CI]" survive.
RE_LOOSE_CITATION = re.compile(
    r"\[[^\[\]]*?(?:\bp\s?\d|\b20\d\d\b|\b19\d\d\b|Source\s*:|\bPI\b|Tabers|"
    r"Taber[’']s|Dorland[’']s|poster|supplement|Appendix|Figure\s+S\d)[^\[\]]*?\]",
    re.I,
)

#: What is left of a citation-styled stretch once its bracket groups are gone
#: still reads as a citation if it carries a page locator ("p2/A", "Sect 2.1").
RE_CITATION_LOCATOR = re.compile(r"\bp\s?\d+\s*/|\bSect\s?\d", re.I)

#: The rest of a citation whose closing bracket was typed without the style:
#: "[YUVIWEL PI 2026 Sect 14.1" (styled) + " p9/A]" (plain).
RE_CITATION_TAIL = re.compile(r"^[^\[\]]{0,80}\](?:\s*\])*")

#: "{Animation: ...}" and similar placeholders for media still to be made.
RE_BRACE_PLACEHOLDER = re.compile(r"\{[^{}]*\}")

RE_SOURCE_URL = re.compile(r"https?://\S+")


def _uncite(text: str) -> tuple[str, bool]:
    """Split a citation-styled stretch into what is really copy.

    Authors paint the citation style over more than the citation: whole
    sentences ("AGV is calculated by dividing..."), a leading "Its", the space
    between two sentences. Only bracket groups are citations. Returns the copy
    that is left and whether a ``[`` was left open (its ``]`` was typed in a
    plain run that follows).
    """
    out: list[str] = []
    depth = 0
    had_bracket = False
    #: What precedes the first bracket - ". " in "achondroplasia. [Jones 2025]"
    #: - ends the sentence before the citation and is kept.
    prefix = text.split("[", 1)[0] if "[" in text else ""
    for ch in text:
        if ch == "[":
            depth += 1
            had_bracket = True
        elif ch == "]":
            had_bracket = True
            if depth:
                depth -= 1
            else:
                # The tail of a citation whose "[" was never typed - everything
                # before this bracket belongs to it.
                out = []
        elif not depth:
            out.append(ch)
    # Placeholders and source URLs (an image's stock-photo link) are not copy.
    kept = RE_SOURCE_URL.sub("", RE_BRACE_PLACEHOLDER.sub("", "".join(out)))
    has_words = re.search(r"[A-Za-z]{2,}|\b[A-Za-z]\b", kept) is not None
    if (had_bracket and not has_words) or RE_CITATION_LOCATOR.search(kept):
        # Separators between citations ("; ", ". "): keep only the spacing so
        # the words either side do not run together.
        lead = prefix.strip()
        if "]" in lead or any(c.isalnum() for c in lead):
            lead = ""
        kept = lead + (" " if any(c.isspace() for c in text) else "")
    return kept, depth > 0


RE_MULTISPACE = re.compile(r"[ \t ]{2,}")
RE_SPACE_BEFORE_PUNCT = re.compile(r"\s+([.,;:!?)])")
RE_DRAWING = re.compile(r"<(?:a:blip|v:imagedata)\b")
RE_EMBED = re.compile(r'<a:blip[^>]*r:embed="([^"]+)"')
RE_VML_ID = re.compile(r'<v:imagedata[^>]*r:id="([^"]+)"')


def _is_symbol_font(name: str | None) -> bool:
    """Is this a dingbat font, i.e. decoration rather than readable text?"""
    if not name:
        return False
    lowered = name.strip().lower()
    return lowered in config.SYMBOL_FONTS_EXACT or any(
        family in lowered for family in config.SYMBOL_FONTS
    )


def drawing_rids(run_xml: str) -> list[str]:
    """Relationship ids of every drawing in a run, in reading order."""
    return RE_EMBED.findall(run_xml) + RE_VML_ID.findall(run_xml)


def slugify_term(text: str) -> str:
    """Stable, HTML-id-safe key for a glossary term."""
    slug = re.sub(r"[^A-Za-z0-9]+", "_", html.unescape(text)).strip("_")
    return (slug or "term")[:48]


@dataclass
class _Token:
    """A stretch of text sharing one formatting signature."""

    text: str
    #: ``(is_glossary_term, bold, italic, superscript, subscript)``
    signature: tuple[bool, bool, bool, bool, bool]


def _join_terms(tokens: list[_Token]) -> list[_Token]:
    """Repair glossary terms the author's styling cut apart.

    * "spinal" + " " + "stenosis", each styled separately, is one term;
    * "analysis of covariance (ANCOVA) mode" + "l ..." - a style that stops
      mid-word - takes the rest of the word into the term.
    """
    merged: list[_Token] = []
    for tok in (_Token(t.text, t.signature) for t in tokens):
        if (
            tok.signature[0]
            and len(merged) >= 2
            and merged[-2].signature == tok.signature
            and not merged[-1].text.strip()
            and merged[-1].signature[1:] == tok.signature[1:]
        ):
            space = merged.pop()
            merged[-1].text += space.text + tok.text
            continue
        merged.append(tok)

    for i, tok in enumerate(merged):
        if not tok.signature[0] or i + 1 >= len(merged):
            continue
        nxt = merged[i + 1]
        if nxt.signature[0] or not tok.text[-1:].isalpha():
            continue
        tail = re.match(r"[A-Za-z]+", nxt.text)
        if tail:
            tok.text += tail.group(0)
            nxt.text = nxt.text[tail.end():]
    return [t for t in merged if t.text]


@dataclass
class InlineResult:
    html: str
    terms: list[GlossaryTerm] = field(default_factory=list)
    #: Relationship ids of drawings in this paragraph, in reading order. Using
    #: rIds rather than a running count keeps the parser exactly in step with
    #: the extractor even when a drawing sits somewhere python-docx and the raw
    #: XML walk disagree about.
    image_rids: list[str] = field(default_factory=list)

    @property
    def has_image(self) -> bool:
        return bool(self.image_rids)


class InlineRenderer:
    """Renders runs to HTML, tracking glossary terms and drawings."""

    def __init__(self, glossary: dict[str, str] | None = None) -> None:
        #: lowercased term text -> definition, from the storyboard's glossary table
        self.glossary = glossary or {}
        self.unmatched_terms: set[str] = set()
        self._rids: list[str] = []
        #: Notes the storyboard addressed to the programmer. Stripped from the
        #: copy, but collected so the report can list what still needs doing.
        #: Word splits them across runs, so they are joined per paragraph.
        self.programming_notes: list[str] = []
        self._note_parts: list[str] = []

    # -- glossary ---------------------------------------------------------

    def lookup_definition(self, term: str) -> str:
        """Match an inline term against the glossary table, tolerantly.

        Authors mark up "monomers" inline but define "monomer" in the table, and
        often mark only the short form of "vitamin A (retinol)". Returns "" when
        nothing matches; the caller decides whether that is worth reporting.
        """
        key = " ".join(term.split()).strip(" .,;:").lower()
        if not key:
            return ""
        candidates = [key, key.rstrip("s"), f"{key}s"]
        if key.endswith("es"):
            # Greek/Latin plurals: "epiphyses" is defined as "epiphysis".
            candidates.append(f"{key[:-2]}is")
        for cand in candidates:
            if cand in self.glossary:
                return self.glossary[cand]
        # Table entries carry a parenthetical, e.g. "thyroxine (T4)"; match on
        # the leading words instead.
        for gk, gv in self.glossary.items():
            head = gk.split("(")[0].strip()
            if head and head in candidates:
                return gv
        for gk, gv in self.glossary.items():
            if key in gk:
                return gv
        # Abbreviation first inline, last in the table: "NT-proBNP (N terminal
        # ...)" is defined as "N-terminal ... (NT-proBNP)".
        abbrev = key.split("(")[0].strip()
        if abbrev:
            for gk, gv in self.glossary.items():
                inner = re.search(r"\(([^)]+)\)", gk)
                if inner and inner.group(1).strip() == abbrev:
                    return gv
        return ""

    def lookup_by_words(self, term: str) -> str:
        """Last resort: an entry whose words all appear, in order, in the term.

        "gain-of-function pathogenic variant" is defined as "gain-of-function
        variant". Only for multi-word entries, and only when the term adds at
        most one word, so a whole clause never borrows a definition.
        """
        words = " ".join(term.split()).strip(" .,;:").lower().split()
        for gk, gv in self.glossary.items():
            entry = gk.split("(")[0].split()
            if len(entry) < 2 or len(words) > len(entry) + 1:
                continue
            it = iter(words)
            if all(w in it for w in entry):
                return gv
        return ""

    def _narrow_spans(self, text: str) -> list[tuple[int, int, str]]:
        """Find the glossary terms sitting inside an over-broad span.

        The storyboard sometimes paints "Glossary item Char" across a whole
        clause ("Recurrent otitis media, potentially leading to conductive
        hearing loss") when only phrases in it are defined terms. Marking the
        clause would put the wrong text in the popup, so mark each defined
        phrase instead, longest first, never overlapping.
        """
        low = text.lower()
        found: list[tuple[int, int, str]] = []
        cands = sorted(
            {
                (cand, gv)
                for gk, gv in self.glossary.items()
                for cand in (gk, gk.split("(")[0].strip())
                if len(cand) >= 4
            },
            key=lambda c: -len(c[0]),
        )
        for cand, gv in cands:
            for m in re.finditer(re.escape(cand), low):
                start, end = m.start(), m.end()
                if any(start < e and s < end for s, e, _ in found):
                    continue
                found.append((start, end, gv))
        return sorted(found)

    # -- runs -------------------------------------------------------------

    def _tokenise(self, runs) -> list[_Token]:
        """Drop noise runs and merge adjacent runs that format identically.

        Word splits a styled phrase into arbitrarily many runs (spell-check
        state, revision ids), so "vitamin A" can arrive as 'v' + 'itamin A'.
        Merging by formatting signature is what makes a glossary term whole
        again. Comment anchors and citation runs are removed *first*, so they
        cannot break the adjacency of the runs around them.
        """
        tokens: list[_Token] = []
        #: Consecutive citation-styled runs (and the whitespace between them),
        #: resolved together because a citation is split across many runs.
        cite: list[str] = []
        cite_sig: tuple[bool, bool, bool, bool, bool] | None = None
        #: A citation left its "[" open: its tail is in the plain runs that
        #: follow. Those runs are held until the "]" shows whether they were
        #: the tail ("Chan 2022 p265/" + "B" + "]") or copy after all.
        open_tail = False
        held: list[tuple[str, tuple]] = []
        #: The tail has closed; stray "] ]" typed after it goes too.
        eat_brackets = False

        def push(text: str, signature) -> None:
            if tokens and tokens[-1].signature == signature:
                tokens[-1].text += text
            else:
                tokens.append(_Token(text=text, signature=signature))

        def release_held() -> None:
            nonlocal open_tail
            for text, signature in held:
                push(text, signature)
            held.clear()
            open_tail = False

        def flush_cite() -> None:
            nonlocal cite, open_tail
            if not cite:
                return
            kept, open_tail = _uncite("".join(cite))
            cite = []
            if kept:
                push(kept, cite_sig)

        for run in runs:
            style = run.style.name if run.style is not None else ""
            if style == config.CHAR_PROGRAMMING_NOTE:
                self._note_parts.append(run.text)
                continue
            # A figure is a figure whatever character style its run carries -
            # authors paste pictures into citation-styled runs too.
            if RE_DRAWING.search(run._r.xml):
                self._rids.extend(drawing_rids(run._r.xml))
                continue
            if style in config.CHAR_IGNORED:
                continue

            font = run.font
            bold = run.bold if run.bold is not None else style in config.CHAR_BOLD
            italic = run.italic if run.italic is not None else style in config.CHAR_ITALIC
            if style in config.CHAR_CITATION:
                if not cite:
                    cite_sig = (False, bold, italic, False, False)
                    if open_tail:
                        # The styled "]" closes the citation: what was held
                        # between the brackets was part of it.
                        held.clear()
                cite.append(run.text)
                continue
            text = run.text
            if cite and not text.strip():
                cite.append(text)  # spacing between two citation runs
                continue
            flush_cite()
            if not text or _is_symbol_font(font.name):
                continue

            signature = (
                style in config.CHAR_GLOSSARY_TERM,
                # Direct formatting beats the character style: a run in a
                # "bold" style with bold switched off displays as regular.
                bold,
                italic,
                bool(font.superscript),
                bool(font.subscript),
            )
            if eat_brackets:
                text = re.sub(r"^\s*\](?:\s*\])*", "", text)
                eat_brackets = not text.strip()
                if not text:
                    continue
            if open_tail:
                tail = RE_CITATION_TAIL.match(text)
                if tail:
                    held.clear()
                    open_tail = False
                    text = text[tail.end():]
                    eat_brackets = not text.strip()
                    if not text:
                        continue
                elif "[" not in text and sum(len(t) for t, _ in held) + len(text) <= 80:
                    held.append((text, signature))
                    continue
                else:
                    release_held()
            push(text, signature)
        flush_cite()
        # No "]" ever came: what was held was copy after all.
        release_held()
        return _join_terms(tokens)

    def _render_token(self, token: _Token) -> tuple[str, list[GlossaryTerm]]:
        is_term, bold, italic, sup, sub = token.signature
        terms: list[GlossaryTerm] = []

        if is_term and token.text.strip():
            out, terms = self._render_term(token.text)
        else:
            out = html.escape(token.text, quote=False)

        if (sup or sub) and not any(c.isalnum() for c in token.text):
            # A superscripted full stop or space is a slip, not a footnote mark.
            sup = sub = False
        if sup:
            out = f"<sup>{out}</sup>"
        elif sub:
            out = f"<sub>{out}</sub>"
        if bold:
            out = f"<strong>{out}</strong>"
        if italic:
            out = f"<em>{out}</em>"
        return out, terms

    def _render_term(self, text: str) -> tuple[str, list[GlossaryTerm]]:
        # Keep surrounding whitespace outside the span so the marked phrase
        # reads cleanly in the popup.
        lead = text[: len(text) - len(text.lstrip())]
        trail = text[len(text.rstrip()) :]
        core = text.strip()
        if not any(c.isalnum() for c in core):
            # A full stop or comma caught by the style is not a term.
            return html.escape(text, quote=False), []

        definition = self.lookup_definition(core)
        if not definition:
            spans = self._narrow_spans(core)
            if spans:
                parts: list[str] = []
                terms: list[GlossaryTerm] = []
                pos = 0
                for start, end, gv in spans:
                    parts.append(self._render_gap(core[pos:start], terms))
                    span, found = self._span(core[start:end], gv)
                    parts.append(span)
                    terms.extend(found)
                    pos = end
                parts.append(self._render_gap(core[pos:], terms))
                return f"{lead}{''.join(parts)}{trail}", terms
            definition = self.lookup_by_words(core)
        if not definition:
            # No definition anywhere: an empty popup helps nobody. The term
            # stays in the copy as plain text and the report lists it.
            self.unmatched_terms.add(core)
            return html.escape(text, quote=False), []

        span, terms = self._span(core, definition)
        return f"{lead}{span}{trail}", terms

    def _render_gap(self, gap: str, terms: list[GlossaryTerm]) -> str:
        """Text between two narrowed terms: itself a term if it is defined.

        "observational" + "cohort study" were styled as one span; the table
        defines "observational study" and "cohort study".
        """
        word = gap.strip(" ,;:")
        definition = self.lookup_definition(word) if len(word) >= 4 else ""
        if not definition:
            return html.escape(gap, quote=False)
        start = gap.index(word)
        span, found = self._span(word, definition)
        terms.extend(found)
        return (html.escape(gap[:start], quote=False) + span
                + html.escape(gap[start + len(word):], quote=False))

    def _span(self, phrase: str, definition: str) -> tuple[str, list[GlossaryTerm]]:
        slug = slugify_term(phrase)
        inner = html.escape(phrase, quote=False)
        span = f"<span class=\"notify g-term\" id='{slug}'>{inner}</span>"
        return span, [GlossaryTerm(slug=slug, text=phrase, definition=definition)]

    def _render_hyperlink(self, link: Hyperlink) -> tuple[str, list[GlossaryTerm]]:
        parts: list[str] = []
        terms: list[GlossaryTerm] = []
        for token in self._tokenise(link.runs):
            frag, found = self._render_token(token)
            parts.append(frag)
            terms.extend(found)
        inner = "".join(parts)
        if not inner:
            return "", terms
        url = html.escape(link.address or "", quote=True)
        if not url:
            return inner, terms
        return f"<a target='_blank' href='{url}'>{inner}</a>", terms

    # -- paragraphs -------------------------------------------------------

    def render(self, para: Paragraph) -> InlineResult:
        """Render one paragraph's inline content (no block wrapper)."""
        self._rids = []
        self._note_parts = []
        parts: list[str] = []
        terms: list[GlossaryTerm] = []

        # Runs are merged within each contiguous stretch; a hyperlink breaks the
        # stretch because it needs its own wrapper.
        pending: list[Run] = []

        def flush_runs() -> None:
            for token in self._tokenise(pending):
                frag, found = self._render_token(token)
                parts.append(frag)
                terms.extend(found)
            pending.clear()

        for child in para.iter_inner_content():
            if isinstance(child, Hyperlink):
                flush_runs()
                frag, found = self._render_hyperlink(child)
                parts.append(frag)
                terms.extend(found)
            else:
                pending.append(child)
        flush_runs()

        note = " ".join("".join(self._note_parts).split()).strip(r" \[]")
        if note:
            self.programming_notes.append(note)

        text = clean_html("".join(parts))
        return InlineResult(html=text, terms=terms, image_rids=list(self._rids))


RE_EMPTY_EMPHASIS = re.compile(r"<(strong|em|sup|sub)>(\s*)</\1>")


def clean_html(text: str) -> str:
    """Tidy the artefacts left behind by stripping citation runs."""
    text = RE_LOOSE_CITATION.sub("", text)
    # Word leaves stray whitespace-only italic/bold runs around edited text.
    for _ in range(3):
        text, n = RE_EMPTY_EMPHASIS.subn(r"\2", text)
        if not n:
            break
    text = RE_MULTISPACE.sub(" ", text)
    # A citation sitting between two sentences leaves ". ." behind - collapse
    # it before the space is tidied away, or it turns into "..". A real
    # ellipsis ("...") is left alone.
    text = re.sub(r"(?<!\.)\.\s+\.(?!\.)", ".", text)
    text = RE_SPACE_BEFORE_PUNCT.sub(r"\1", text)
    text = re.sub(r"(?<!\.)\.\.(?!\.)", ".", text)
    return text.strip()


def wrap(tag: str, inner: str, attrs: str = "") -> str:
    if not inner:
        return ""
    return f"<{tag}{(' ' + attrs) if attrs else ''}>{inner}</{tag}>"


def paragraphs_to_html(chunks: list[tuple[str, str]]) -> str:
    """Assemble ``(kind, html)`` chunks into a body string.

    ``kind`` is ``p``, ``li1``, ``li2``, ``num`` or ``raw``; consecutive list
    items collapse into a single list, with level-2 items nested inside the
    preceding level-1. ``num`` items form an ``<ol>``; ``raw`` is emitted
    verbatim, which is how a table drops into the middle of body copy.
    """
    out: list[str] = []
    open_l1 = False
    open_l2 = False
    open_ol = False

    def close_lists() -> None:
        nonlocal open_l1, open_l2, open_ol
        if open_l2:
            out.append("</ul></li>")
            open_l2 = False
        if open_l1:
            out.append("</ul>")
            open_l1 = False
        if open_ol:
            out.append("</ol>")
            open_ol = False

    for kind, frag in chunks:
        if not frag:
            continue
        if kind == "num":
            if open_l1 or open_l2:
                close_lists()
            if not open_ol:
                out.append("<ol>")
                open_ol = True
            out.append(f"<li>{frag}</li>")
            continue
        if kind == "raw":
            close_lists()
            out.append(frag)
            continue
        if open_ol:
            out.append("</ol>")
            open_ol = False
        if kind == "li1":
            if open_l2:
                out.append("</ul></li>")
                open_l2 = False
            if not open_l1:
                out.append("<ul>")
                open_l1 = True
            out.append(f"<li>{frag}")
            # left open so a following level-2 item can nest; closed below
            out.append("</li>")
        elif kind == "li2":
            if not open_l1:
                out.append("<ul>")
                open_l1 = True
                out.append("<li>")
            elif out and out[-1] == "</li>":
                out.pop()  # reopen the level-1 item to nest inside it
            if not open_l2:
                out.append("<ul>")
                open_l2 = True
            out.append(f"<li>{frag}</li>")
        else:
            close_lists()
            out.append(f"<p>{frag}</p>")

    close_lists()
    # A list whose items carry bullet icons takes the authored course's class,
    # and an icon item's sub-list sits inside its <div>, beside the icon.
    body = "".join(out).replace(
        f"<ul><li><img class='{config.LIST_ICON_CLASS}'",
        f"<ul class='{config.LIST_ICON_LIST_CLASS}'><li><img class='{config.LIST_ICON_CLASS}'",
    )
    return re.sub(
        rf"(<li><img class='{config.LIST_ICON_CLASS}'[^>]*> <div>.*?)</div>(<ul>.*?</ul>)</li>",
        r"\1\2</div></li>",
        body,
    )
