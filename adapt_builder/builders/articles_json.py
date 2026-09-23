"""articles.json - one record per article, plus assessment configuration."""

from __future__ import annotations

from .. import config
from ..model import Article


def _assessment(article: Article) -> dict:
    return {
        "_isEnabled": True,
        "_id": article.assessment_id,
        "_suppressMarking": False,
        "_scoreToPass": article.score_to_pass or config.ASSESSMENT_SCORE_TO_PASS,
        "_correctToPass": 0,
        "_isPercentageBased": True,
        "_includeInTotalScore": False,
        "_assessmentWeight": 1,
        "_isResetOnRevisit": False,
        "_attempts": config.ASSESSMENT_ATTEMPTS,
        "_allowResetIfPassed": True,
        "_scrollToOnReset": False,
        "_banks": {"_isEnabled": False, "_split": "2,1", "_randomisation": False},
        "_randomisation": {"_isEnabled": False, "_blockCount": 1},
        "_questions": {
            "_resetIncorrectOnly": True,
            "_resetType": "hard",
            "_comment": (
                "For 'soft', when using trickle, please set the trickle "
                "Completion Attribute to `_isInteractionComplete'."
            ),
            "_canShowFeedback": True,
            "_canShowMarking": True,
            "_canShowModelAnswer": False,
        },
    }


def build(article: Article, article_id: str, page_id: str) -> dict:
    data = {
        "_id": article_id,
        "_parentId": page_id,
        "_type": "article",
        "_classes": "",
        "title": article.title,
        "displayTitle": article.display_title,
        "body": "",
        "instruction": "",
    }

    if article.page_level_progress is not None:
        data["_pageLevelProgress"] = {"_isEnabled": article.page_level_progress}

    if article.is_assessment:
        data["_assessment"] = _assessment(article)

    return data
