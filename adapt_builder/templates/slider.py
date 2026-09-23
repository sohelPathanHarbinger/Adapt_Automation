"""adapt-contrib-slider: pick a number on a scale.

The storyboard states the scale as "Scale: 1 to 10" and the answer as a number
or a range; anything it leaves out falls back to the defaults here, which are
deliberately obvious rather than silently plausible.
"""

from __future__ import annotations

from ..model import Component
from .base import Ctx
from .question import question_component

DEFAULT_START = 1
DEFAULT_END = 10
DEFAULT_STEP = 1


def build(component: Component, ctx: Ctx) -> dict:
    extra = component.extra

    data = question_component(
        component,
        ctx,
        "slider",
        instruction="Drag the slider to make your choice and select Submit.",
    )
    data["ariaScaleName"] = ""
    data["labelStart"] = extra.get("labelStart", "")
    data["labelEnd"] = extra.get("labelEnd", "")
    data["_scaleStart"] = extra.get("scaleStart", DEFAULT_START)
    data["_scaleEnd"] = extra.get("scaleEnd", DEFAULT_END)
    data["_scaleStep"] = extra.get("scaleStep", DEFAULT_STEP)
    data["scaleStepPrefix"] = ""
    data["scaleStepSuffix"] = ""
    data["_showNumber"] = True
    data["_showScaleIndicator"] = True
    data["_showScale"] = True
    data["_showScaleNumbers"] = True

    answer = extra.get("correctAnswer")
    bottom, top = extra.get("correctBottom"), extra.get("correctTop")
    if answer is not None:
        data["_correctAnswer"] = answer
        data["_correctRange"] = {"_bottom": "", "_top": ""}
    elif bottom is not None and top is not None:
        data["_correctAnswer"] = ""
        data["_correctRange"] = {"_bottom": bottom, "_top": top}
    else:
        data["_correctAnswer"] = ""
        data["_correctRange"] = {"_bottom": "", "_top": ""}
        ctx.report.warn(
            f"{ctx.id}: slider has no correct answer or range - set "
            "_correctAnswer or _correctRange"
        )
    return data
