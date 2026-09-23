"""adapt-contrib-assessmentResults - the Results block of a Check Your Progress."""

from __future__ import annotations

from ..model import Component
from .base import Ctx, base_component

RETRY_PROMPT = "Retry Check Your Progress questions?"

BANDS = [
    {"_score": 0, "feedbackNotFinal": RETRY_PROMPT, "feedback": "", "_allowRetry": True},
    {"_score": 25, "feedbackNotFinal": RETRY_PROMPT, "feedback": "", "_allowRetry": True},
    {"_score": 50, "feedbackNotFinal": RETRY_PROMPT, "feedback": "", "_allowRetry": True},
    {"_score": 80, "feedbackNotFinal": RETRY_PROMPT, "feedback": "", "_allowRetry": True},
    {
        "_score": 100,
        "feedback": "Congratulations!",
        "_allowRetry": False,
        "_classes": "high-score",
    },
]


def build(component: Component, ctx: Ctx) -> dict:
    data = base_component(component, ctx, "assessmentResults")
    data["title"] = "Results"
    data["displayTitle"] = ""
    data["_assessmentId"] = component.extra.get("_assessmentId", "")
    data["_isVisibleBeforeCompletion"] = True
    data["_comment"] = "setCompletionOn = inview | pass"
    data["_setCompletionOn"] = "inview"
    data["_isOptional"] = True
    data["_resetType"] = "inherit"
    data["_retry"] = {"button": "Retry", "feedback": "", "_routeToAssessment": True}
    data["_completionBody"] = (
        "You got {{{score}}} out of {{{maxScore}}} correct. {{{feedback}}}"
    )
    data["_bands"] = BANDS
    data["_pageLevelProgress"] = {"_isEnabled": True}
    return data
