"""adapt-contrib-hotgraphic.

The storyboard gives hotspot copy but no pin coordinates, so pins are laid out
on an evenly spaced arc across the top of the image. Every generated hotgraphic
is listed in the report as needing manual pin placement.
"""

from __future__ import annotations

from ..model import Component
from .base import Ctx, base_component


def _pin_positions(count: int) -> list[tuple[float, float]]:
    """Evenly spaced starting positions, deliberately obvious as placeholders."""
    if count <= 0:
        return []
    step = 80.0 / max(count, 1)
    return [(10.0 + (i % 2) * 12.0, round(5.0 + i * step, 1)) for i in range(count)]


def build(component: Component, ctx: Ctx) -> dict:
    data = base_component(component, ctx, "hotgraphic")
    data["title"] = component.title or "Hot graphic"
    data["_classes"] = component.classes or "hotgraphic-vertical"
    data["mobileBody"] = ""
    data["mobileInstruction"] = (
        "Select the plus icon followed by the next arrow to find out more."
    )
    data["_comment"] = "setCompletionOn = inview | allItems"
    data["_setCompletionOn"] = "allItems"
    data["_canCycleThroughPagination"] = False
    data["_hidePagination"] = False
    data["_isNarrativeOnMobile"] = True
    data["_useNumberedPins"] = True
    data["_useGraphicsAsPins"] = False
    data["_isRound"] = False

    src = component.figure.src if component.figure else ""
    alt = component.figure.caption if component.figure else ""
    attribution = component.extra.get("attribution", "")
    data["_graphic"] = {
        "src": src,
        "alt": alt or attribution,
        "attribution": (
            f"<span class='img-footnote no-image-title-text'>{attribution}</span>"
            if attribution
            else ""
        ),
    }

    untitled = [n for n, item in enumerate(component.items, start=1) if not item.title]
    if untitled:
        ctx.report.warn(
            f"{ctx.id}: hotspot(s) {', '.join(map(str, untitled))} have no title in "
            "the storyboard (just 'Hotspot N') - their popups open untitled"
        )

    # Pins the parser could place itself - over each photo of a composed
    # backdrop - beat the evenly spaced placeholders.
    computed = component.extra.get("pins")
    positions = computed or _pin_positions(len(component.items))
    if computed:
        # Read and removed by inherit.py; base/Source may still override.
        data["_pinSource"] = "panels"
    data["_items"] = [
        {
            "_top": top,
            "_left": left,
            "title": item.title,
            "body": item.body,
            "strapline": item.title,
            "_imageAlignment": "",
            "_comment": (
                "Supported classes = 'hide-desktop-image' | 'hide-popup-image'. "
                "Additional classes can be used but they must be predefined in "
                "one of the Less files"
            ),
            "_classes": "",
            "_graphic": {"src": "", "alt": "", "attribution": "", "_classes": ""},
            "_tooltip": {"_isEnabled": False, "text": "{{ariaLabel}}"},
            "_pin": {"src": "", "alt": ""},
        }
        for item, (top, left) in zip(component.items, positions)
    ]

    data["_pageLevelProgress"] = {"_isEnabled": True}
    data["_graphicExpand"] = {
        "_isEnabled": True,
        "_button": {
            "buttonText": "",
            "ariaLabel": "Enlarge image",
            "iconClass": "graphic-expand-icon",
        },
        "_selector": "",
    }

    if not computed:
        ctx.report.warn(
            f"{ctx.id}: hotgraphic pin coordinates are placeholders - "
            f"set _top/_left for its {len(component.items)} hotspot(s)"
        )
    return data
