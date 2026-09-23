"""Working out what course a storyboard describes.

The course title is not body copy, so it has to come from the document's
metadata. This storyboard family carries it in two places — the Word document
properties and the running header — and both agree. Falling back to the
filename keeps the build working on a document that has neither.
"""

from __future__ import annotations

import html
import re
import zipfile
from pathlib import Path

from .. import config

RE_HEADER_PART = re.compile(r"word/header\d*\.xml")
RE_TEXT = re.compile(r"<w:t[^>]*>(.*?)</w:t>", re.S)
#: Review-stage suffixes that are part of the storyboard's name, not the
#: course's. A separator is required before each one so that version tokens
#: inside the title ("Mod D1v1") survive.
RE_TRAILING_NOISE = re.compile(
    r"[\s_-]+(?:programming[\s_-]*QC|print(?:[\s_-]*v?\d+(?:[._]\d+)*)?|final|draft)"
    r"[\s_-]*$",
    re.I,
)


def _normalise(text: str) -> str:
    """Collapse whitespace, including the padding Word puts around symbols."""
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    # "Attruby ® Product Module" -> "Attruby® Product Module"
    for symbol in config.TRADEMARK_ENTITIES:
        text = text.replace(f" {symbol}", symbol)
    return text


def _from_properties(document) -> str:
    try:
        return _normalise(document.core_properties.title or "")
    except (AttributeError, KeyError):
        return ""


def _from_header(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            for name in sorted(n for n in archive.namelist() if RE_HEADER_PART.fullmatch(n)):
                xml = archive.read(name).decode("utf8", errors="replace")
                text = _normalise("".join(RE_TEXT.findall(xml)))
                if text:
                    return text
    except (OSError, zipfile.BadZipFile, KeyError):
        pass
    return ""


def _from_filename(path: Path) -> str:
    """Last resort: tidy the filename into something presentable."""
    stem = re.sub(r"[_-]+", " ", path.stem)
    # Storyboards are named for their review stage, which is not part of the
    # course title; strip a couple of those suffixes if present.
    previous = None
    while previous != stem:
        previous = stem
        stem = RE_TRAILING_NOISE.sub("", stem)
    return _normalise(stem)


def extract_title(document, path: Path) -> tuple[str, str]:
    """Return ``(title, source)`` for the course this storyboard describes."""
    if config.COURSE_TITLE_OVERRIDE:
        return config.COURSE_TITLE_OVERRIDE, "config.COURSE_TITLE_OVERRIDE"

    for value, source in (
        (_from_properties(document), "the Word document properties"),
        (_from_header(path), "the page header"),
        (_from_filename(path), "the storyboard filename"),
    ):
        if value:
            return value, source
    return config.COURSE_TITLE_FALLBACK, "config.COURSE_TITLE_FALLBACK"


def as_plain(title: str) -> str:
    """Title for ``course.title`` — entities, but no markup."""
    for symbol, entity in config.TRADEMARK_ENTITIES.items():
        title = title.replace(symbol, entity)
    return title


def as_html(title: str) -> str:
    """Title for display — trademark symbols raised to superscript."""
    for symbol, entity in config.TRADEMARK_ENTITIES.items():
        title = title.replace(symbol, f"<sup>{entity}</sup>")
    return title
