"""adapt-tabs (horizontal and vertical layouts)."""

from __future__ import annotations

from ..model import Component
from .base import Ctx, base_component


def build(component: Component, ctx: Ctx) -> dict:
    data = base_component(component, ctx, "tabs")
    data["title"] = component.title or "Tabs"
    data["_classes"] = component.classes or "image-padding-removed"
    data["_tabLayout"] = component.extra.get("_tabLayout", "horizontal")
    data["_minHeight"] = ""
    data["_comment"] = (
        "Only set min height if you want to uniform the content container size "
        "across tab items. By default, the container will display at the height "
        "of each item's content"
    )
    data["_items"] = [
        {
            "tabTitle": item.tab_title or item.title,
            "title": "",
            "body": item.body,
            "_classes": "",
            "_graphic": {
                "alt": item.figure.caption if item.figure else "",
                "src": item.figure.src if item.figure else "",
            },
        }
        for item in component.items
    ]
    data["_pageLevelProgress"] = {"_isEnabled": True}
    return data
