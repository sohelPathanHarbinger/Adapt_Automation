"""config.json.

Framework-level configuration - spoor, accessibility, completion criteria. The
storyboard has no bearing on any of it, so this is a faithful passthrough of the
existing file, normalised to the project's JSON formatting.
"""

from __future__ import annotations

from pathlib import Path

from .. import config
from ..jsonio import read_json
from ..report import Report

FALLBACK = {
    "_defaultLanguage": "en",
    "_defaultDirection": "ltr",
    "_questionWeight": 1,
    "_completionCriteria": {
        "_requireContentCompleted": True,
        "_requireAssessmentCompleted": False,
        "_shouldSubmitScore": True,
        "_submitOnEveryAssessmentAttempt": True,
    },
    "_spoor": {"_isEnabled": True},
    "build": {"strictMode": True},
}


def build(report: Report, course_dir: Path | None = None) -> dict:
    """``course_dir`` points at ``src/course``."""
    source = (course_dir or config.COURSE_SOURCE / "src" / "course") / "config.json"
    if source.is_file():
        return read_json(source)
    report.warn(f"{source} not found - config.json built from a minimal fallback")
    return dict(FALLBACK)
