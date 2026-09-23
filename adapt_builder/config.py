"""Central configuration: paths, Word style names, and course-level constants.

Everything that is "policy" rather than "logic" lives here so the storyboard
conventions can be retuned without touching the parser or the templates.
"""

from __future__ import annotations

import re
from pathlib import Path

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent

#: One folder per course, each holding that course's storyboard .docx, print
#: PDF and assets/. The folder name is the course name.
INPUTS_DIR = ROOT / "Inputs"

#: The authored Adapt course every build starts from and inherits player
#: settings from. Its theme and language folders are discovered, never
#: assumed - see :mod:`adapt_builder.paths`.
COURSE_SOURCE = ROOT / "base" / "Source"

OUTPUT_DIR = ROOT / "Output"

#: Where --no-copy puts its JSON. Deliberately outside Output/, so a normal
#: build leaves nothing there but the staged course itself.
SCRATCH_DIR = ROOT / "_scratch"
BACKUP_DIR = ROOT / "_backups"

#: Used only when a source tree has no language folder to discover.
DEFAULT_LANG = "en"

# Theme asset folders, relative to ``src/theme/<theme>/assets``.

#: Player art: background, logo, nav buttons, callout icons. A course's own
#: Player overlay (Inputs/<course>/assets/images/Player) lands here.
PLAYER_DIR = "GUI"

#: Theme asset folders kept as they are when a course is staged. Everything
#: else under assets/ (images, videos, audios, pdf) is the base course's own
#: media and is cleared, so a course ships only what its storyboard produced
#: and what it delivered itself.
KEEP_THEME_ASSETS = {PLAYER_DIR}

#: Where the figures extracted from the storyboard are written. They are the
#: course's own artwork, so they sit with the other course images rather than
#: among the player art. Set FIGURE_SUBDIR to keep them in a sub-folder.
FIGURE_DIR = "images"
FIGURE_SUBDIR = ""
FIGURE_SRC_PREFIX = "/".join(part for part in ("assets", FIGURE_DIR, FIGURE_SUBDIR) if part)

# --------------------------------------------------------------------------
# Word paragraph styles -> structural role
# --------------------------------------------------------------------------

STYLE_PAGE = {"Heading 1"}
STYLE_ARTICLE = {"Heading 2"}
STYLE_BLOCK = {"Heading 3", "Heading 4", "Heading 5"}

STYLE_BODY = {
    "Normal",
    ">NXL_Normal",
    "il Body Text",
    "toc 1",
    # Word's built-in list style, used loosely by some storyboards for
    # reference entries and stray paragraphs alike.
    "List Paragraph",
    "pop-up",
}
STYLE_BULLET_L1 = {"Bullet list level 1", "bull 1", "Bullet-List"}
STYLE_BULLET_L2 = {"Bullet list level 2", "Bullet-2", "bullet list 2"}

#: Numbered lists. In a References section these are the reference entries;
#: elsewhere they render as an ordered list.
STYLE_ORDERED = {"Number bullet list 1"}

#: Captions. ``Diagram label 1`` labels both figures ("Figure 1-3: ...") and
#: tables ("Table 1-1: ..."), so a caption is held until the next figure or
#: table decides which it belongs to.
STYLE_CAPTION = {"footnote/diagram label", "Diagram label 1", "Figure-Table-Label"}

#: Whole paragraphs that are medical/legal source citations. Like the
#: ``Refrence text Char`` run style, they exist for review only - dropped.
STYLE_DROP = {"Refrence text"}

#: Whole paragraphs addressed to the programmer ("Programming Note: Display
#: image side by side..."). Their text goes to the report, never the course -
#: but a drawing inside one is still a figure, and an ``Interactivity:`` label
#: typed in this style is still a label.
STYLE_PROGRAMMING_NOTE = {"Programming-Note"}

STYLE_INTERACT_H1 = "Interactivity-Heading-1"
STYLE_INTERACT_H2 = "Interactivity-Heading-2"
STYLE_INTERACT_BODY = "Interactivity-body"
STYLE_INTERACT_BULLET = {"Interactivity-Bullet-1"}
STYLE_INTERACT_BULLET_L2 = {"Interactive-bullet-2", "Interactivity-Bullet-2"}
STYLE_INTERACT_LABEL = "Interactivity-Label"

STYLE_CYP_QUESTION = "CYP-Question"
#: Every spelling of the question style. Some storyboards set it with an en
#: dash ("CYP – Question"); all of them are treated as STYLE_CYP_QUESTION.
STYLE_CYP_QUESTIONS = {STYLE_CYP_QUESTION, "CYP – Question"}
STYLE_CYP_ANSWER = {"CYP - Answer", "CYP - TrueFalse", "CYP – Answer", "CYP–TrueFalse"}

STYLE_REFERENCE = {"il Reference"}

# --------------------------------------------------------------------------
# Word character styles -> inline meaning
# --------------------------------------------------------------------------

#: Runs in this character style are glossary terms; they become
#: ``<span class="notify g-term" id='...'>`` plus a ``_notifyAnywhere`` entry.
CHAR_GLOSSARY_TERM = {"Glossary item Char", "Glossary Item"}

#: Runs in these styles are source citations (``[Attruby PI p2/A]``) that are
#: present for medical/legal review only and never ship to the learner.
CHAR_CITATION = {"Refrence text Char", "il Inline Reference", "Reference Text"}

#: Word comment anchors and notes addressed to the programmer
#: ("[Please remove superscript 'a' from the figure]") - always dropped from
#: the copy. Programming notes are collected into the report instead, because
#: they are instructions someone still has to act on.
CHAR_IGNORED = {"annotation reference"}
CHAR_PROGRAMMING_NOTE = "Programming-Notes"

#: A character style that only means "bold". Storyboards that came through
#: Word Online carry it instead of direct bold formatting.
CHAR_BOLD = {"Bold", "Strong", "bold"}

#: The same for italic - Word's built-in "Emphasis", used for journal titles
#: in reference lists.
CHAR_ITALIC = {"Emphasis", "Italic", "italic"}

#: Dingbat fonts. The storyboard sets callout icons in these (a magnifier for
#: ZOOM IN), and the glyph decodes to an unrelated letter once the font is
#: dropped - "Å ZOOM IN". Runs in these fonts are decoration, not copy.
SYMBOL_FONTS = ("wingdings", "webdings", "marlett")
SYMBOL_FONTS_EXACT = ("symbol",)

# --------------------------------------------------------------------------
# Interactivity label -> component template
# --------------------------------------------------------------------------

INTERACTIVITY_PREFIX = "interactivity:"

INTERACTIVITY_MAP = {
    "accordion": "accordion",
    "accordions": "accordion",
    "tab": "tabs",
    "tabs": "tabs",
    "horizontal tabs": "tabs",
    "vertical tabs": "tabs",
    "hot spots": "hotgraphic",
    "hotspots": "hotgraphic",
    "hot spot": "hotgraphic",
    "hotspot": "hotgraphic",
    "hotspot image": "hotgraphic",
    "hot spot image": "hotgraphic",
    "hotspot images": "hotgraphic",
    "hot spot images": "hotgraphic",
    "callout": "callout",
    # A callout labelled by its kind rather than as "Callout".
    "zoom in": "callout",
    "quick fact": "callout",
    # Every component whose plugin ships in base/Source can be asked for by
    # name. The spellings are the ones a storyboard author would reasonably
    # type; add another here rather than teaching the parser about it.
    "narrative": "narrative",
    "carousel": "narrative",
    "graphic mcq": "gmcq",
    "image mcq": "gmcq",
    "gmcq": "gmcq",
    "slider": "slider",
    "graphic slider": "graphicSlider",
    "image slider": "graphicSlider",
    "text input": "textinput",
    "textinput": "textinput",
    "fill in the blank": "textinput",
    "table": "table",
    "text with popups": "textwithpopup",
    "popups": "textwithpopup",
    "spacer": "blank",
    "blank": "blank",
}

#: Some storyboards label an interactivity as ``<Type>: <Title>`` - "Accordion:
#: Learning Objectives" - instead of ``Interactivity: <Type>``. The type is
#: then the first word and the rest is the interactivity's own heading.
INTERACTIVITY_ALT_TYPES = {
    "accordion",
    "accordions",
    "tabs",
    "tab",
    "hot spots",
    "hotspots",
    "narrative",
    "table",
}

#: "End Interactivity: Accordions" closes the open interactivity. Without this
#: the label leaks into the course as body copy.
INTERACTIVITY_END_PREFIX = "end interactivity"

#: Interactivity labels whose tabs render vertically.
VERTICAL_TAB_LABELS = {"vertical tabs"}

#: Recognised ``Accordion 1:`` / ``Tab 2:`` / ``Hot spot 3:`` item prefixes.
ITEM_PREFIX_WORDS = ("accordion", "tab", "hot spot", "hotspot")

# --------------------------------------------------------------------------
# Callouts (adapt-hint extension)
# --------------------------------------------------------------------------

HINT_ICONS = {
    "zoom in": "icon-hint-zoom-in",
    "quick fact": "icon-hint-quick-fact",
    # "FAST FORWARD / FLASH BACK" is one callout type with a combined icon, so
    # "flash back" is tried first; a lone "FAST FORWARD" gets its own icon.
    "flash back": "icon-hint-flash-back",
    "fast forward": "icon-hint-fast-forward",
}
DEFAULT_HINT_ICON = "icon-hint-zoom-in"

# --------------------------------------------------------------------------
# Tables
# --------------------------------------------------------------------------
# A storyboard table is one of four things, told apart by where it sits and
# what its header row says. Anything unrecognised falls through to a data
# table, which is the safe default: the content ships and a human can restyle
# it, rather than being silently dropped.

#: Rendered onto every data table so the theme can size its columns.
TABLE_CLASSES = "column-width-fix"

#: Wrapper classes on the text component a data table becomes.
TABLE_COMPONENT_CLASSES = "flip"

#: A narration / on-screen-text table is the script for a Key Concepts video.
#: Recognised by its first-row headers; the copy is not learner-facing HTML,
#: it is the spec for a video someone still has to produce.
TABLE_NARRATION_HEADERS = ("narration",)
TABLE_ONSCREEN_HEADERS = ("on screen text", "on-screen text", "onscreen text")

#: Folder and naming for the media components those tables become.
MEDIA_SUBDIR = "videos"
MEDIA_SRC_PREFIX = "assets/videos"
MEDIA_POSTER = "assets/videos/poster.png"

#: A matching question's table pairs a list of things with lettered stems.
#: The letter column is what the Answers copy of the table fills in.
MATCHING_INSTRUCTION = "Choose an option from each dropdown list and select Submit."
MATCHING_PLACEHOLDER = "Please select an option"

# --------------------------------------------------------------------------
# Page / article naming conventions in the storyboard
# --------------------------------------------------------------------------

TITLE_GLOSSARY = "glossary"
TITLE_REFERENCES = "references"
TITLE_CHECK_YOUR_PROGRESS = "check your progress"
TITLE_ANSWERS = "answers"
TITLE_KEY_CONCEPTS = "key concepts"

#: Some storyboards author Key Concepts twice: once as print copy and once as
#: the video script. The print copy is for the PDF only and is not built; the
#: programming copy is built under the plain "Key Concepts" title.
TITLE_PRINT_ONLY = ("(for print)",)
TITLE_PROGRAMMING_SUFFIX = ("(for programming)",)

#: On a Key Concepts page the narration table is the chapter summary, and the
#: authored course presents that as an accordion - one panel per topic, like
#: Learning Objectives - rather than as a video. The narration is still
#: published in the report for whoever records the avatar voiceover.
#: Elsewhere a narration table remains a media component.
KEY_CONCEPTS_AS_ACCORDION = True
TITLE_LEARNING_OBJECTIVES = "learning objectives"

#: "How to Use This Module" is print copy in the storyboard ("The programmed
#: Adapt page should mirror the Figma template"). The Figma template is the same
#: in every module: four rows, a line of help beside its player icon from
#: assets/GUI. Set HOW_TO_USE_TEMPLATE to False to build the storyboard's copy.
TITLE_HOW_TO_USE = "how to use this module"
HOW_TO_USE_TEMPLATE = True
HOW_TO_USE_TEXT_CLASSES = "grid__column-8 help"
HOW_TO_USE_ICON_CLASSES = "grid__column-6 help"
HOW_TO_USE_ROWS = [
    (
        "<p>This module has interactive components, such as accordions, tabs, and "
        "hotspots, that must be completed before moving forward.</p><p>Selecting the "
        "progress bar at the top right of the screen will display all the interactive "
        "components within the chapter. Once the progress bar is filled, you can move "
        "on to the next chapter.</p>",
        "assets/GUI/progress.png",
    ),
    (
        "<p>At the end of each chapter, answer the &ldquo;Check Your Progress&rdquo; "
        "questions to complete the chapter.</p>",
        "assets/GUI/cyp.png",
    ),
    (
        "<p>Glossary terms are highlighted throughout this module. The glossary can "
        "also be accessed by selecting the menu on the right.</p>",
        "assets/GUI/glossary.png",
    ),
    (
        "<p>Select the Quick Fact! and Zoom In icons at the margins to display "
        "callouts with additional information.</p>",
        "assets/GUI/callout.png",
    ),
]

#: A programming note containing this phrase ("Display image side by side with
#: paragraph below") lays the pictures beside the copy next to the note.
SIDE_BY_SIDE_PHRASE = "side by side"

#: A picture no larger than this (either side, px) pasted into a list item is
#: the item's bullet icon, marked up as the authored course does:
#: <ul class='custom-img-bullet'><li><img class='bullet-img' ...><div>...</div>.
#: A larger picture there is a figure, placed after the list.
LIST_ICON_MAX_PX = 200
LIST_ICON_CLASS = "bullet-img"
LIST_ICON_LIST_CLASS = "custom-img-bullet"

#: Pages that carry a chapter assessment and page-level progress tracking.
CHAPTER_TITLE_PREFIX = "chapter"

# --------------------------------------------------------------------------
# Assessment defaults
# --------------------------------------------------------------------------

ASSESSMENT_SCORE_TO_PASS = 75
ASSESSMENT_ATTEMPTS = 2

# --------------------------------------------------------------------------
# Page navigation component
# --------------------------------------------------------------------------

NAV_CONFIDENTIAL = (
    "<div style='font-weight:700'>Confidential. For internal reference and/or "
    "training purposes only. Do not copy, modify, or distribute externally.</div>"
)
NAV_COMPLETE_INTERACTIONS = (
    "<div style='font-weight:700'>Be sure that all callouts and interactivities "
    "are completed before moving forward.<br>Select the progress bar at the top "
    "right of the screen for any missed interactions.<p></p></div>"
)

# --------------------------------------------------------------------------
# Pages the storyboard does not describe but the course requires
# --------------------------------------------------------------------------

#: ``body`` is a format string; ``{title}`` is the course title as HTML, so the
#: page names whatever course was actually built.
SYNTHETIC_PAGES = [
    {
        "slug": "congratulations",
        "title": "Congratulations",
        "displayTitle": "Congratulations",
        "body": (
            '<h4 class="mb-0">You\'ve completed the <strong><span '
            'class="title-color"><i>{title}</i></span></strong>. You may exit '
            "the course by clicking the &ldquo;X&rdquo; in the upper right of "
            "the browser window in which you viewed the course. Thank you.</h4>"
        ),
    }
]

# --------------------------------------------------------------------------
# Course-level values
# --------------------------------------------------------------------------

#: Course title. ``None`` derives it from the storyboard — document properties
#: first, then the page header, then the filename. Set a string to force one.
COURSE_TITLE_OVERRIDE: str | None = None

#: Fallback when a storyboard carries no title anywhere.
COURSE_TITLE_FALLBACK = "Course"

#: Symbols that read as superscript in the player.
TRADEMARK_ENTITIES = {"®": "&reg;", "™": "&trade;", "©": "&copy;"}

BACKGROUND_IMAGE = "assets/GUI/background.png"

# --------------------------------------------------------------------------
# Per-course overlays under Inputs/<course>/
# --------------------------------------------------------------------------
# Everything here is optional. A course that ships none of it builds exactly
# as base/Source dictates.

#: High-resolution originals of the storyboard's figures. Each one replaces the
#: bitmap embedded in the .docx that it matches visually, so files can be named
#: however the art team delivers them ("Figure 1-2A.jpg", "iStock-123.jpg").
COURSE_IMAGES_DIR = "assets/images/Course"

#: Player (theme GUI) images, laid out exactly like the theme's assets/GUI
#: folder. A file overwrites the theme file at the same relative path; one
#: with no counterpart there is reported and skipped.
PLAYER_IMAGES_DIR = "assets/images/Player"

#: Files copied over the staged theme folder at the same relative path - the
#: course's own palette and branding (e.g. less/zz-course-theme.less).
THEME_OVERLAY_DIR = "theme"

#: A storyboard figure and a delivered original are the same picture when
#: their downsampled greyscale images correlate at least this well, and their
#: aspect ratios agree within ASPECT_TOLERANCE.
IMAGE_MATCH_THRESHOLD = 0.95
IMAGE_ASPECT_TOLERANCE = 0.08

#: Delivered originals are often print resolution (8000 px, 17 MB). Anything
#: wider or taller than this is scaled down before it ships.
IMAGE_MAX_SIDE = 2000

# --------------------------------------------------------------------------
# Print PDF offered through the Resources drawer
# --------------------------------------------------------------------------

PDF_SUBDIR = "pdf"
PDF_SRC_PREFIX = "assets/pdf"

PRINT_PDF_TITLE = "Print"
PRINT_PDF_DESCRIPTION = "PDF Version of the module"
