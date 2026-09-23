"""adapt-contrib-graphic, with adapt-graphicExpand for full-size viewing."""

from __future__ import annotations

from ..model import Component
from .base import Ctx, base_component


def build(component: Component, ctx: Ctx) -> dict:
    data = base_component(component, ctx, "graphic")
    src = component.extra.get("src", "")
    alt = component.extra.get("alt", "")
    attribution = component.extra.get("attribution", "")

    data["_graphic"] = {
        "alt": alt,
        "large": src,
        "small": src,
        "attribution": (
            f"<span class='img-footnote no-image-title-text'>{attribution}</span>"
            if attribution
            else ""
        ),
    }
    data["_graphicExpand"] = {
        # Player icons (the How to Use rows) are not figures to enlarge.
        "_isEnabled": component.extra.get("expand", True),
        "_button": {
            "buttonText": "",
            "ariaLabel": "Enlarge image",
            "iconClass": "graphic-expand-icon",
        },
        "_selector": "",
    }
    data["_pageLevelProgress"] = {
        "_isEnabled": False,
        "_isCompletionIndicatorEnabled": False,
    }
    return data
