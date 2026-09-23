"""adapt-contrib-gmcq: a multiple-choice question whose options are images.

Identical to ``mcq`` in how it is answered and marked; the difference is that
each option carries a picture, so the storyboard has to supply one per option.
"""

from __future__ import annotations

from ..model import Component
from .base import Ctx
from .question import ensure_question, question_component


def build(component: Component, ctx: Ctx) -> dict:
    question = ensure_question(component, ctx, "gmcq")

    data = question_component(
        component,
        ctx,
        "gmcq",
        instruction=(
            "Choose all that apply then select Submit."
            if question.select_all
            else "Choose one option then select Submit."
        ),
        classes="margin-bottom_1 hide-reset-btn",
    )
    data["_selectable"] = question.selectable
    data["_canShowModelAnswer"] = False
    data["_canShowCorrectness"] = True
    data["_items"] = [
        {
            "text": option.text,
            "altText": "",
            "_shouldBeSelected": option.correct,
            "_isPartlyCorrect": False,
            "_graphic": {
                "alt": "",
                "attribution": "",
                "large": "",
                "small": "",
            },
        }
        for option in question.options
    ]

    if not any(o.correct for o in question.options):
        ctx.report.warn(f"{ctx.id}: no correct answer resolved from the answer key")
    ctx.report.note(
        f"{ctx.id}: gmcq option images are empty - set _graphic.large/small on "
        "each option"
    )
    return data
