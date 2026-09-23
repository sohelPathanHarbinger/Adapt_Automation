"""Shared scaffolding for the question components.

Every question in this course answers the same way - two attempts, feedback on,
marking shown, interaction recorded - and repeats the same feedback copy. That
was duplicated across each question template; it lives here instead, so
changing how questions behave is one edit rather than six.
"""

from __future__ import annotations

from .. import config
from ..model import Component, Question
from .base import Ctx, base_component


def ensure_question(component: Component, ctx: Ctx, kind: str) -> Question:
    """The component's question, or an empty one with the reason reported.

    A question component always has a question when it came through Check Your
    Progress. It can arrive without one when a storyboard asks for a question
    type as an interactivity, which cannot express an answer key - so the build
    emits the component with nothing in it and says so, rather than stopping.
    """
    if component.question is not None:
        return component.question
    ctx.report.warn(
        f"{ctx.id}: {kind} has no question - a question type has to be authored "
        "under 'Check Your Progress' so it has an answer key. The component was "
        "written out empty."
    )
    return Question(body=component.body)


def _feedback(reset_hint: bool) -> dict:
    """The standard feedback block.

    ``reset_hint`` picks the wording for a component the learner has to reset
    before retrying, rather than simply changing an answer in place.
    """
    retry = (
        "Please select reset and try again." if reset_hint else "Please try again."
    )
    incorrect = {
        "notFinal": f"<h3 style='margin-bottom: 6px;'>Incorrect</h3>{retry}",
        "final": (
            "<h3 style='margin-bottom: 6px;'>Incorrect</h3>"
            "Please review the correct answer before moving on."
        ),
    }
    return {
        "title": "Feedback",
        "altTitle": "Alt feedback title text",
        "correct": (
            "<h3 style='margin-bottom: 6px;'>Correct!</h3>"
            "You have selected the correct response."
        ),
        "_incorrect": dict(incorrect),
        "_partlyCorrect": dict(incorrect),
    }


#: The two flavours in use. ``FEEDBACK`` is the plain one; ``FEEDBACK_RESET``
#: is for components whose answers must be reset before a second attempt.
FEEDBACK = _feedback(reset_hint=False)
FEEDBACK_RESET = _feedback(reset_hint=True)


def question_component(
    component: Component,
    ctx: Ctx,
    adapt_name: str,
    *,
    instruction: str,
    classes: str = "margin-bottom_1",
    reset_hint: bool = False,
) -> dict:
    """A component with the question defaults already applied.

    Callers add whatever is specific to their component type - ``_items``,
    a scale, an answer list - and are expected to leave the rest alone.
    """
    data = base_component(component, ctx, adapt_name)
    data["_classes"] = component.classes or classes
    data["displayTitle"] = ""
    data["instruction"] = instruction
    data["ariaQuestion"] = ""
    data["_attempts"] = config.ASSESSMENT_ATTEMPTS
    data["_shouldDisplayAttempts"] = False
    data["_isRandom"] = False
    data["_questionWeight"] = 1
    data["_hasItemScoring"] = False
    data["_canShowModelAnswer"] = True
    data["_canShowCorrectness"] = False
    data["_canShowFeedback"] = True
    data["_canShowMarking"] = True
    data["_recordInteraction"] = True
    data["_feedback"] = FEEDBACK_RESET if reset_hint else FEEDBACK
    data["_pageLevelProgress"] = {"_isEnabled": True}
    return data
