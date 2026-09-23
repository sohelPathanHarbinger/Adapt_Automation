"""adapt-contrib-mcq, driven by the CYP question / answer-key pairs."""

from __future__ import annotations

from ..model import Component
from .base import Ctx
from .question import ensure_question, question_component


def build(component: Component, ctx: Ctx) -> dict:
    question = ensure_question(component, ctx, "mcq")

    data = question_component(
        component,
        ctx,
        "mcq",
        instruction=(
            "Choose all that apply then select Submit."
            if question.select_all
            else "Choose one option then select Submit."
        ),
        classes="margin-bottom_1 hide-reset-btn",
    )
    # An mcq marks itself rather than revealing a model answer.
    data["_selectable"] = question.selectable
    data["_canShowModelAnswer"] = False
    data["_canShowCorrectness"] = True
    data["_items"] = [
        {
            "text": option.text,
            "altText": "",
            "_shouldBeSelected": option.correct,
            "_isPartlyCorrect": False,
        }
        for option in question.options
    ]

    if not any(option.correct for option in question.options):
        ctx.report.warn(f"{ctx.id}: no correct answer resolved from the answer key")
    if len(question.options) < 2:
        ctx.report.warn(
            f"{ctx.id}: only {len(question.options)} option(s) parsed for this question"
        )
    return data
