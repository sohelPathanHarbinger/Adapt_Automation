"""adapt-pageNav - the previous / home / next bar closing every page."""

from __future__ import annotations

from ..model import Component
from .base import Ctx, base_component


def _button(
    enabled: bool,
    icon: str,
    text: str,
    aria: str,
    *,
    icon_comment: str = "",
    align_right: bool = False,
    route: bool = True,
) -> dict:
    button = {
        "_isEnabled": enabled,
        "_lockUntilPageComplete": False,
        "_order": 1,
        "_classes": "",
        "_iconClassComment": icon_comment,
        "_iconClass": icon,
        "_alignIconRight": align_right,
        "text": text,
        "ariaLabel": aria,
        "_showTooltip": False,
        "tooltip": "{{displayTitle}}",
    }
    if route:
        button["_customRouteId"] = ""
    return button


def build(component: Component, ctx: Ctx) -> dict:
    data = base_component(component, ctx, "pageNav")
    data["title"] = component.title or "Nav"
    data["displayTitle"] = ""
    data["_loopStyleComment"] = {
        "allPages": "loop sequentially through all pages in course",
        "siblings": "loop sequentially through all pages in current parent object",
        "none": (
            "disable previous and next buttons at start and end of the pages in "
            "the current parent object"
        ),
    }
    data["_loopStyle"] = "none"
    data["_shouldSkipOptionalPages"] = False
    data["_buttons"] = {
        "_returnToPreviousLocation": _button(
            False, "", "Return", "Return to previous location", route=False
        ),
        "_previous": _button(
            True,
            "icon-controls-left",
            "",
            "Previous Page",
            icon_comment="Suggested icon = 'icon-controls-left'",
        ),
        "_root": _button(
            True,
            "icon-home",
            "",
            "Go to main menu",
            icon_comment="Suggested icon = 'icon-home'",
        ),
        "_up": _button(False, "", "Back to menu", "Back to menu"),
        "_next": _button(
            True,
            "icon-controls-right",
            "",
            "Next Page",
            icon_comment="Suggested icon = 'icon-controls-right'",
            align_right=True,
        ),
        "_sibling": _button(False, "", "{{inc index}}", "Page {{inc index}}"),
        "_close": _button(
            False,
            "",
            "Close",
            "Close window",
            icon_comment="Suggested icon = 'icon-cross'",
            route=False,
        ),
    }
    data["_buttons"]["_close"]["tooltip"] = "Close window"
    return data
