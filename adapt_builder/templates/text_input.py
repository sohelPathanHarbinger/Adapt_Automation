"""adapt-contrib-textInput: the learner types the answer.

Each blank is one item, and an item accepts several spellings of the same
answer - the storyboard's answer key is split on "/" or "," to get them.
"""

from __future__ import annotations

from ..model import Component
from .base import Ctx
from .question import question_component


def build(component: Component, ctx: Ctx) -> dict:
    question = component.question
    answers = component.extra.get("answers") or (
        [[o.text for o in question.options]] if question and question.options else []
    )

    data = question_component(
        component,
        ctx,
        "textinput",
        instruction="Input your answer and select Submit.",
    )
    data["_items"] = [
        {
            "_answers": list(group),
            "prefix": "",
            "suffix": "",
            "placeholder": "Enter answer here",
        }
        for group in answers
        if group
    ]

    if not data["_items"]:
        ctx.report.warn(f"{ctx.id}: text input question has no accepted answers")
    return data
