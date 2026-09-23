"""Path resolution.

Everything the build touches is discovered at run time rather than hard-coded:
which course is being built, where its storyboard and print PDF live, and where
inside the Adapt source tree the theme and language folders sit. That keeps the automation working for the
next course, and the next theme, without edits.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from . import config

DOCX_GLOB = "*.docx"
PDF_GLOB = "*.pdf"


def _real(paths) -> list[Path]:
    """Drop Word's ``~$`` lock files and other hidden noise."""
    return sorted(p for p in paths if not p.name.startswith(("~$", ".")))


def sanitise_name(text: str) -> str:
    """Collapse anything that is not a letter or digit into single underscores."""
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_") or "course"


# ---------------------------------------------------------------------------
# Inputs/<course name>/
# ---------------------------------------------------------------------------


@dataclass
class InputCourse:
    """One course's source material under ``Inputs/``."""

    name: str
    root: Path
    storyboard: Path
    print_pdf: Path | None = None
    assets: Path | None = None

    @property
    def output_name(self) -> str:
        """Folder name used under ``Output/`` - the course folder's own name."""
        return sanitise_name(self.name)

    def _optional_dir(self, relative: str) -> Path | None:
        path = self.root / relative
        return path if path.is_dir() else None

    @property
    def course_images(self) -> Path | None:
        """Delivered originals of the storyboard's figures, if any."""
        return self._optional_dir(config.COURSE_IMAGES_DIR)

    @property
    def player_images(self) -> Path | None:
        """Theme GUI images for this course, laid out like ``assets/GUI``."""
        return self._optional_dir(config.PLAYER_IMAGES_DIR)

    @property
    def theme_overlay(self) -> Path | None:
        """Files copied over the staged theme - the course's own branding."""
        return self._optional_dir(config.THEME_OVERLAY_DIR)


def list_input_courses(inputs_dir: Path | None = None) -> list[str]:
    """Course folder names under ``Inputs/`` that contain a storyboard.

    A folder without a ``.docx`` is not a course - a stray copy of some other
    project's source tree, say - so it is passed over rather than offered.
    """
    inputs_dir = inputs_dir or config.INPUTS_DIR
    if not inputs_dir.is_dir():
        return []
    return [
        d.name
        for d in _real(p for p in inputs_dir.iterdir() if p.is_dir())
        if _real(d.glob(DOCX_GLOB))
    ]


def resolve_input_course(name: str, inputs_dir: Path | None = None) -> InputCourse:
    """Locate one course's storyboard, print PDF and assets.

    ``name`` is the folder name under ``Inputs/``; a path to the folder works
    too, so tab-completion in a shell does the right thing.
    """
    inputs_dir = inputs_dir or config.INPUTS_DIR

    candidate = Path(name)
    root = candidate if candidate.is_dir() else inputs_dir / name
    if not root.is_dir():
        available = list_input_courses(inputs_dir)
        listing = "\n  ".join(available) if available else "(none found)"
        raise SystemExit(
            f"error: no course folder '{name}' in {inputs_dir}\n"
            f"available courses:\n  {listing}"
        )

    storyboards = _real(root.glob(DOCX_GLOB))
    if not storyboards:
        raise SystemExit(f"error: no .docx storyboard in {root}")
    storyboard = max(storyboards, key=lambda p: p.stat().st_mtime)

    pdfs = _real(root.glob(PDF_GLOB))
    assets = root / "assets"

    return InputCourse(
        name=root.name,
        root=root,
        storyboard=storyboard,
        print_pdf=pdfs[0] if pdfs else None,
        assets=assets if assets.is_dir() else None,
    )


# ---------------------------------------------------------------------------
# An Adapt source tree (base/Source, or a staged copy of it)
# ---------------------------------------------------------------------------


@dataclass
class CourseTree:
    """Resolved locations inside an Adapt course source tree."""

    root: Path
    course_dir: Path  # src/course
    lang: str  # e.g. "en"
    theme: Path  # src/theme/<theme-name>

    @property
    def lang_dir(self) -> Path:
        return self.course_dir / self.lang

    @property
    def theme_assets(self) -> Path:
        return self.theme / "assets"

    @property
    def figures_dir(self) -> Path:
        figures = self.theme_assets / config.FIGURE_DIR
        return figures / config.FIGURE_SUBDIR if config.FIGURE_SUBDIR else figures

    @property
    def pdf_dir(self) -> Path:
        return self.theme_assets / config.PDF_SUBDIR


def find_theme(src_root: Path) -> Path | None:
    """The project theme under ``src/theme``.

    Adapt builds exactly one theme, so when there is a single directory it is
    unambiguous. If a project ever carries several, the one that is not a
    vanilla/base theme wins.
    """
    theme_root = src_root / "theme"
    if not theme_root.is_dir():
        return None
    themes = _real(p for p in theme_root.iterdir() if p.is_dir())
    if not themes:
        return None
    if len(themes) == 1:
        return themes[0]
    preferred = [t for t in themes if "vanilla" not in t.name.lower()]
    return (preferred or themes)[0]


def find_language(course_dir: Path, default: str = "en") -> str:
    """The language folder inside ``src/course`` (``en``, ``fr``, ...)."""
    if not course_dir.is_dir():
        return default
    langs = _real(p for p in course_dir.iterdir() if p.is_dir())
    if not langs:
        return default
    for lang in langs:
        if lang.name == default:
            return default
    return langs[0].name


def resolve_course_tree(root: Path, default_lang: str = "en") -> CourseTree:
    """Describe an Adapt source tree, discovering its theme and language."""
    src = root / "src"
    course_dir = src / "course"
    theme = find_theme(src)
    if theme is None:
        raise SystemExit(
            f"error: no theme found under {src / 'theme'} - is {root} an Adapt "
            "course source tree?"
        )
    return CourseTree(
        root=root,
        course_dir=course_dir,
        lang=find_language(course_dir, default_lang),
        theme=theme,
    )
