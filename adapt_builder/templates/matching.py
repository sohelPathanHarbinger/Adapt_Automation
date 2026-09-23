"""adapt-contrib-matching, driven by a Check Your Progress pairing table.

The storyboard authors a matching question as two copies of one table: the
Check Your Progress copy leaves the letter column blank, and the Answers copy
fills it in. Reading both is what resolves which subject belongs to which stem.
"""

from __future__ import annotations

from .. import config
from ..model import Component
from .base import Ctx
from .question import ensure_question, question_component

def build(component: Component, ctx: Ctx) -> dict:
    question = ensure_question(component, ctx, "matching")

    data = question_component(
        component,
        ctx,
        "matching",
        instruction=config.MATCHING_INSTRUCTION,
        reset_hint=True,
    )
    data["_shouldResetAllAnswers"] = False
    data["_isRandom"] = True
    data["_isRandomQuestionOrder"] = False
    data["_canShowMarking"] = False
    data["placeholder"] = config.MATCHING_PLACEHOLDER

    # A question that sorts items into categories reuses a category: two
    # outcomes are both "Secondary outcome". Offering it twice in the dropdown
    # is noise, and demanding a unique answer per row would make the question
    # impossible - so both only apply when every option really is distinct.
    options = list(dict.fromkeys(question.match_options))
    data["_allowOnlyUniqueAnswers"] = len(options) == len(question.match_options)

    # One dropdown per lettered stem; every subject is offered in each, and the
    # answer key says which single subject is the right one.
    by_letter = question.match_answers
    items = []
    for letter, text in question.stems:
        correct = by_letter.get(letter, "")
        items.append(
            {
                "text": text,
                "_options": [
                    {
                        "text": option,
                        "_isCorrect": option == correct,
                        "_score": 1 if option == correct else 0,
                    }
                    for option in options
                ],
            }
        )
        if not correct:
            ctx.report.warn(
                f"{ctx.id}: matching stem '{letter}' has no subject in the "
                "Answers table - no correct option was set"
            )

    data["_items"] = items

    if not items:
        ctx.report.warn(f"{ctx.id}: matching question parsed no stems")
    if not question.match_options:
        ctx.report.warn(f"{ctx.id}: matching question parsed no options")
    return data
