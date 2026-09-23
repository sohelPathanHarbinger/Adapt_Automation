"""adapt-contrib-blank: a deliberate empty component.

Used for spacing, so it carries no copy at all - not even a title. It is also
the host for a callout that has nothing of its own to hang on: two callouts in
a row, where the component above already carries one.
"""

from __future__ import annotations

from ..model import Component
from .base import Ctx, hint_block, notify_items


def build(component: Component, ctx: Ctx) -> dict:
    data = {
        "_id": ctx.id,
        "_parentId": ctx.parent_id,
        "_type": "component",
        "_component": "blank",
        "_classes": component.classes,
        "_layout": component.layout,
        "_isOptional": True,
    }
    hint = hint_block(component.hint)
    if hint:
        data["_hint"] = hint
        notify = notify_items(component.hint.terms)
        if notify:
            data["_notifyAnywhere"] = notify
    return data
