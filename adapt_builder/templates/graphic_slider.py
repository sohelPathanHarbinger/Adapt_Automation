"""adapt-contrib-graphicSlider: a slider that swaps the image as it moves."""

from __future__ import annotations

from ..model import Component
from .base import Ctx, base_component, with_page_level_progress


def build(component: Component, ctx: Ctx) -> dict:
    data = base_component(component, ctx, "graphicSlider")
    data["displayTitle"] = component.display_title
    data["_graphicSlider"] = {
        "alt": component.figure.caption if component.figure else "",
        "longdescription": "",
        "large": component.figure.src if component.figure else "",
        "small": component.figure.src if component.figure else "",
        "attribution": component.extra.get("attribution", ""),
    }
    # One image per stop on the scale; the storyboard supplies them in order.
    data["_items"] = [
        {
            "_graphic": {
                "alt": item.figure.caption if item.figure else item.title,
                "large": item.figure.src if item.figure else "",
                "small": item.figure.src if item.figure else "",
            },
            "text": item.body or item.title,
        }
        for item in component.items
    ]
    data["_scaleStart"] = 1
    data["_scaleEnd"] = max(len(component.items), 1)
    data["_scaleStep"] = 1
    data["_showScale"] = True
    data["_showScaleNumbers"] = True

    if not component.items:
        ctx.report.warn(f"{ctx.id}: graphic slider has no stops")
    return with_page_level_progress(data, True)
