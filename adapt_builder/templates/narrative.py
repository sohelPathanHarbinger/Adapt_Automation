"""adapt-contrib-narrative: a sequence of panels the learner steps through.

Shaped like an accordion in the storyboard - a heading per panel with its copy
underneath - so it is parsed the same way and only differs in how it renders.
"""

from __future__ import annotations

from ..model import Component
from .base import Ctx, base_component, with_page_level_progress


def build(component: Component, ctx: Ctx) -> dict:
    data = base_component(component, ctx, "narrative")
    data["displayTitle"] = component.display_title
    data["instruction"] = (
        "Select the next and back arrows to find out more."
    )
    data["mobileInstruction"] = (
        "Select the plus icon followed by the next arrow to find out more."
    )
    data["_hasNavigationInTextArea"] = False
    data["_setCompletionOn"] = "allItems"
    data["_isTextBelowImage"] = False
    data["_isMobileTextBelowImage"] = False
    data["_items"] = [
        {
            "title": item.title,
            "body": item.body,
            "strapline": item.title,
            "_graphic": {
                "src": item.figure.src if item.figure else "",
                "alt": item.figure.caption if item.figure else "",
                "attribution": "",
            },
        }
        for item in component.items
    ]

    if not component.items:
        ctx.report.warn(f"{ctx.id}: narrative has no panels")
    if not any(i.figure for i in component.items):
        ctx.report.note(
            f"{ctx.id}: narrative has no images - each panel's _graphic.src is "
            "empty and needs filling in"
        )
    return with_page_level_progress(data, True)
