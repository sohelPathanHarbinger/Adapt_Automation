"""adapt-contrib-selectchoice, driven by a Check Your Progress grid table.

The storyboard authors these as a table with one statement per row and a
column per choice, an X marking the column that applies. The X is the answer
key, so unlike an mcq these questions need nothing from the Answers section.
"""

from __future__ import annotations

from .. import config
from ..model import Component
from .base import Ctx
from .question import ensure_question, question_component

BLANK_GRAPHIC = {"alt": "", "large": "", "small": ""}


def build(component: Component, ctx: Ctx) -> dict:
    question = ensure_question(component, ctx, "selectchoice")

    data = question_component(
        component,
        ctx,
        "selectchoice",
        instruction=(
            "Select " + " or ".join(question.choices) + " for each row."
            if question.choices
            else "Select an option for each row."
        ),
    )
    data["_shouldResetAllAnswers"] = False
    data["_canShowMarking"] = False
    data["_choices"] = [
        {"text": choice, "_graphic": dict(BLANK_GRAPHIC)} for choice in question.choices
    ]
    data["_items"] = [
        {
            "text": text,
            "_graphic": dict(BLANK_GRAPHIC),
            "_shouldBeSelected": answer,
        }
        for text, answer in question.grid_items
    ]

    if not question.choices:
        ctx.report.warn(f"{ctx.id}: grid question parsed no choice columns")
    if not question.grid_items:
        ctx.report.warn(f"{ctx.id}: grid question parsed no rows")
    return data
