"""Shared scaffolding for every component template."""

from __future__ import annotations

from dataclasses import dataclass

from ..model import Callout, Component, GlossaryTerm
from ..report import Report


@dataclass
class Ctx:
    """Everything a template needs beyond the component itself."""

    id: str
    parent_id: str
    report: Report


def notify_items(terms: list[GlossaryTerm]) -> list[dict[str, str]]:
    """De-duplicate glossary terms by slug, preserving first-seen order."""
    seen: dict[str, GlossaryTerm] = {}
    for term in terms:
        if term.slug not in seen:
            seen[term.slug] = term
    return [t.as_notify() for t in seen.values()]


def hint_block(callout: Callout | None) -> dict | None:
    """Render a storyboard callout as an ``adapt-hint`` configuration."""
    if callout is None:
        return None
    return {
        "_isEnabled": True,
        "title": callout.title,
        "altTitle": "",
        "body": callout.body,
        "_imageAlignment": "right",
        "_graphic": {
            "_src": callout.figure.src if callout.figure else "",
            "alt": callout.figure.caption if callout.figure else "",
            "attribution": "",
        },
        "_button": {
            "_iconClass": callout.icon_class,
            "_alignIconRight": False,
            "text": "",
            "ariaLabel": callout.title,
        },
    }


def base_component(component: Component, ctx: Ctx, adapt_name: str) -> dict:
    """The field set every component in this course shares, in a stable order."""
    data: dict = {
        "_id": ctx.id,
        "_parentId": ctx.parent_id,
        "_type": "component",
        "_component": adapt_name,
        "_classes": component.classes,
        "_layout": component.layout,
        "title": component.title,
        "displayTitle": component.display_title,
        "body": component.body,
        "instruction": component.instruction,
    }

    notify = notify_items(component.terms)
    if notify:
        data["_notifyAnywhere"] = notify

    hint = hint_block(component.hint)
    if hint:
        data["_hint"] = hint
        # Terms used only inside the callout still need a definition source.
        extra = notify_items(component.hint.terms) if component.hint else []
        if extra:
            merged = {item["id"]: item for item in data.get("_notifyAnywhere", [])}
            for item in extra:
                merged.setdefault(item["id"], item)
            data["_notifyAnywhere"] = list(merged.values())

    return data


def with_page_level_progress(data: dict, enabled: bool) -> dict:
    data["_pageLevelProgress"] = {"_isEnabled": enabled}
    return data
