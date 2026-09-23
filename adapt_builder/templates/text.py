"""adapt-contrib-text."""

from __future__ import annotations

from ..model import Component
from .base import Ctx, base_component


def build(component: Component, ctx: Ctx) -> dict:
    data = base_component(component, ctx, "text")
    data["_onScreen"] = {
        "_isEnabled": False,
        "_classes": "",
        "_percentInviewVertical": 50,
    }
    data["_search"] = {"_isEnabled": True, "keywords": ""}
    data["_pageLevelProgress"] = {
        "_isEnabled": False,
        "_isCompletionIndicatorEnabled": False,
    }
    return data
