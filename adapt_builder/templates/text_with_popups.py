"""adapt-textWithPopups: body copy whose highlighted phrases open a popup.

Each storyboard item becomes one popup: its heading is the link text and its
copy is what the popup shows.
"""

from __future__ import annotations

from ..model import Component
from .base import Ctx, base_component, with_page_level_progress


def build(component: Component, ctx: Ctx) -> dict:
    data = base_component(component, ctx, "textwithpopup")
    data["displayTitle"] = component.display_title
    data["_popups"] = [
        {
            "_id": f"popup-{n}",
            "title": item.title,
            "body": item.body,
            "linkText": item.title,
        }
        for n, item in enumerate(component.items, start=1)
    ]

    if not component.items:
        ctx.report.warn(f"{ctx.id}: text with popups has no popups")
    return with_page_level_progress(data, True)
