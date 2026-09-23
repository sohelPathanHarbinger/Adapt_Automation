"""adapt-contrib-accordion."""

from __future__ import annotations

from ..model import Component
from .base import Ctx, base_component


def build(component: Component, ctx: Ctx) -> dict:
    data = base_component(component, ctx, "accordion")
    data["title"] = component.title or "Accordion"
    data["_shouldCollapseItems"] = True
    data["_shouldExpandFirstItem"] = False
    data["_comment"] = "setCompletionOn = inview | allItems"
    data["_setCompletionOn"] = "allItems"
    data["_isCenterAligned"] = False
    data["_items"] = [
        {
            "title": item.title,
            "body": item.body,
            "_titleIcon": "",
            "_imageAlignment": "",
            "_graphic": {
                "src": item.figure.src if item.figure else "",
                "alt": item.figure.caption if item.figure else "",
                "attribution": "",
            },
            "_classes": "",
        }
        for item in component.items
    ]
    data["_pageLevelProgress"] = {"_isEnabled": True}
    return data
