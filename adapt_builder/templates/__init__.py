"""Component templates, keyed by the ``kind`` set on a parsed component.

Each module turns one parsed component into the JSON that Adapt's matching
plugin expects. Adding support for a new component means adding a module here
and wiring it into :data:`TEMPLATES` - nothing in the parser or the builders
needs to change.

Every component listed here has its plugin installed in ``base/Source``;
:mod:`adapt_builder.validate` checks that at build time, because emitting a
component whose plugin is missing produces a course that silently fails to
render it.
"""

from __future__ import annotations

from ..model import Component
from . import (
    accordion,
    assessment_results,
    blank,
    gmcq,
    graphic,
    graphic_slider,
    hotgraphic,
    matching,
    mcq,
    media,
    narrative,
    page_nav,
    selectchoice,
    slider,
    table,
    tabs,
    text,
    text_input,
    text_with_popups,
)
from .base import Ctx

TEMPLATES = {
    # Content
    "text": text.build,
    "graphic": graphic.build,
    "media": media.build,
    "blank": blank.build,
    "table": table.build,
    "textwithpopup": text_with_popups.build,
    # Interactivities
    "accordion": accordion.build,
    "tabs": tabs.build,
    "narrative": narrative.build,
    "hotgraphic": hotgraphic.build,
    "graphicSlider": graphic_slider.build,
    # Questions
    "mcq": mcq.build,
    "gmcq": gmcq.build,
    "matching": matching.build,
    "selectchoice": selectchoice.build,
    "slider": slider.build,
    "textinput": text_input.build,
    # Course furniture
    "assessmentResults": assessment_results.build,
    "pageNav": page_nav.build,
}

#: ``_component`` value -> the plugin folder that has to be installed for it.
#: Used by :mod:`adapt_builder.validate` to catch a component the staged course
#: cannot actually render.
PLUGIN_FOR_COMPONENT = {
    "accordion": "adapt-contrib-accordion",
    "assessmentResults": "adapt-contrib-assessmentResults",
    "blank": "adapt-contrib-blank",
    "gmcq": "adapt-contrib-gmcq",
    "graphic": "adapt-contrib-graphic",
    "graphicSlider": "adapt-contrib-graphicSlider",
    "hotgraphic": "adapt-contrib-hotgraphic",
    "matching": "adapt-contrib-matching",
    "mcq": "adapt-contrib-mcq",
    "media": "adapt-contrib-media",
    "narrative": "adapt-contrib-narrative",
    "pageNav": "adapt-pageNav",
    "selectchoice": "adapt-selectchoice",
    "slider": "adapt-contrib-slider",
    "table": "adapt-table",
    "tabs": "adapt-tabs",
    "text": "adapt-contrib-text",
    "textinput": "adapt-contrib-textInput",
    "textwithpopup": "adapt-textWithPopups",
}

__all__ = ["TEMPLATES", "PLUGIN_FOR_COMPONENT", "Ctx", "render"]


def render(component: Component, ctx: Ctx) -> dict:
    builder = TEMPLATES.get(component.kind)
    if builder is None:
        ctx.report.warn(f"{ctx.id}: no template for component kind '{component.kind}'")
        return TEMPLATES["text"](component, ctx)
    return builder(component, ctx)
