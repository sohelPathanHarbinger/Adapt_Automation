"""course.json.

Most of this file describes player chrome the storyboard says nothing about -
drawer labels, audio settings, accessibility strings, resources. Those are read
from the existing course and preserved; only the parts the storyboard owns are
replaced: the title, the glossary, and the tracking-id high-water mark.
"""

from __future__ import annotations

from pathlib import Path

from .. import config
from ..docx_reader.title import as_html, as_plain
from ..jsonio import read_json
from ..model import Storyboard
from ..report import Report


def _skeleton() -> dict:
    return {
        "_id": "course",
        "_type": "course",
        "_classes": "",
        "_htmlClasses": "",
        "title": "",
        "displayTitle": "",
        "description": "",
        "body": "",
        "instruction": "",
        "_lockType": "sequential",
        "_globals": {"_moduleTitle": ""},
        "_latestTrackingId": 0,
        "_glossary": {
            "_isEnabled": True,
            "_drawerOrder": 1,
            "title": "Glossary",
            "description": "Select here to view the glossary for this course",
            "_isIndexEnabled": False,
            "_isGroupHeadersEnabled": False,
            "_isSearchEnabled": True,
            "_glossaryItems": [],
        },
    }


def _set_resources(data: dict, print_pdf: str, report: Report) -> None:
    """Point the Resources drawer at this course's print PDF.

    The inherited link names the previous module's PDF, so it is replaced
    outright rather than merged.
    """
    resources = data.setdefault("_resources", {})
    others = [
        item
        for item in resources.get("_resourcesItems", [])
        if item.get("title") != config.PRINT_PDF_TITLE
    ]

    if not print_pdf:
        resources["_resourcesItems"] = others
        report.warn(
            "no .pdf in this course's Inputs folder - the Resources drawer has "
            "no 'Print' download"
        )
        return

    others.insert(
        0,
        {
            "_type": "document",
            "title": config.PRINT_PDF_TITLE,
            "description": config.PRINT_PDF_DESCRIPTION,
            "_link": f"{config.PDF_SRC_PREFIX}/{print_pdf}",
            "filename": print_pdf,
            "_forceDownload": True,
        },
    )
    resources["_resourcesItems"] = others
    report.note(f"Resources drawer links the print PDF '{print_pdf}'")


def build(
    storyboard: Storyboard,
    latest_tracking_id: int,
    report: Report,
    course_dir: Path | None = None,
    lang: str = config.DEFAULT_LANG,
    print_pdf: str = "",
) -> dict:
    """``course_dir`` points at ``src/course``; the file itself lives under it."""
    source = (course_dir or config.COURSE_SOURCE / "src" / "course") / lang / "course.json"

    if source.is_file():
        data = read_json(source)
        report.note(
            "course.json player settings (audio, drawer, resources, "
            "accessibility) were preserved from the existing course"
        )
    else:
        data = _skeleton()
        report.warn(f"{source} not found - course.json built from a minimal skeleton")

    # Course identity comes from the storyboard, never from the base course -
    # otherwise a new module would ship under the previous one's name.
    data["title"] = as_plain(storyboard.title)
    data["body"] = as_html(storyboard.title)
    data.setdefault("_globals", {})["_moduleTitle"] = as_html(storyboard.title)
    data["_latestTrackingId"] = latest_tracking_id

    _set_resources(data, print_pdf, report)

    glossary = data.setdefault("_glossary", _skeleton()["_glossary"])
    glossary["_isEnabled"] = True
    glossary["_glossaryItems"] = [
        {"term": term.text, "description": term.definition}
        for term in storyboard.glossary
    ]
    report.count("glossary items in course.json", len(glossary["_glossaryItems"]))

    return data
