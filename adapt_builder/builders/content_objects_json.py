"""contentObjects.json - one record per page."""

from __future__ import annotations

from .. import config
from ..model import Page

BACKGROUND = {
    "_xlarge": config.BACKGROUND_IMAGE,
    "_large": config.BACKGROUND_IMAGE,
    "_medium": config.BACKGROUND_IMAGE,
    "_small": config.BACKGROUND_IMAGE,
}

EMPTY_RESPONSIVE = {"_xlarge": "", "_large": "", "_medium": "", "_small": ""}


def build(page: Page, page_id: str) -> dict:
    return {
        "_id": page_id,
        "_parentId": "course",
        "_type": "page",
        "_classes": "",
        "_htmlClasses": "",
        "title": page.title,
        "displayTitle": page.display_title or page.title,
        "body": "",
        "pageBody": "",
        "instruction": "",
        "_graphic": {"src": "", "alt": ""},
        "linkText": "View",
        "_pageLevelProgress": {
            "_isEnabled": page.is_chapter,
            "_showPageCompletion": False,
            "_isCompletionIndicatorEnabled": False,
            "_excludeAssessments": True,
        },
        "_vanilla": {
            "_backgroundImage": dict(BACKGROUND),
            "_backgroundStyles": {
                "_backgroundSize": "cover",
                "_backgroundRepeat": "no-repeat",
                "_backgroundPosition": "fixed",
            },
            "_responsiveClasses": dict(EMPTY_RESPONSIVE),
            "_pageHeader": {
                "_textAlignment": {"_title": "", "_body": "", "_instruction": ""},
                "_backgroundImage": dict(EMPTY_RESPONSIVE),
                "_backgroundStyles": {
                    "_backgroundSize": "",
                    "_backgroundRepeat": "",
                    "_backgroundPosition": "",
                },
                "_minimumHeights": {
                    "_xlarge": 0,
                    "_large": 0,
                    "_medium": 0,
                    "_small": 0,
                },
            },
        },
    }
