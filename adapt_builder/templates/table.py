"""adapt-table: a real table component, as an alternative to HTML in body copy.

A storyboard's data tables become HTML inside a ``text`` component by default,
which is what the hand-authored courses do. This template is for the case where
a table is wanted as a component in its own right - asked for explicitly with
an ``Interactivity: Table`` label - so it can be styled and sized on its own.
"""

from __future__ import annotations

from ..model import Component
from .base import Ctx, base_component, with_page_level_progress

DEFAULT_MIN_WIDTH = 800


def build(component: Component, ctx: Ctx) -> dict:
    rows = component.extra.get("rows") or []

    data = base_component(component, ctx, "table")
    data["displayTitle"] = component.display_title
    data["_rowHeaderIndexes"] = ""
    data["_colHeaderIndexes"] = component.extra.get("colHeaderIndexes", "0")
    data["_minWidth"] = component.extra.get("minWidth", DEFAULT_MIN_WIDTH)
    data["_rows"] = [
        {
            "_classes": "",
            "_cells": [
                {
                    "_colSpan": str(cell.get("colspan", 1)),
                    "_rowSpan": str(cell.get("rowspan", 1)),
                    "text": cell.get("text", ""),
                    "_classes": "",
                    "_isHeading": bool(cell.get("heading")),
                    "_graphic": {"_src": "", "alt": "", "attribution": ""},
                }
                for cell in row
            ],
        }
        for row in rows
    ]

    if not rows:
        ctx.report.warn(f"{ctx.id}: table component has no rows")
    return with_page_level_progress(data, True)
