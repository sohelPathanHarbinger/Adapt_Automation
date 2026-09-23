"""Storyboard tree -> the five course JSON documents.

The walk happens once, in document order, so IDs and tracking IDs are assigned
consistently across contentObjects / articles / blocks / components.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import config
from ..docx_reader.title import as_html
from ..model import Article, Block, Component, Page, Storyboard
from ..report import Report
from ..templates import Ctx, render
from . import (
    articles_json,
    blocks_json,
    config_json,
    content_objects_json,
    course_json,
)
from .ids import IdAllocator, page_slug


@dataclass
class CourseJson:
    config: dict
    course: dict
    content_objects: list[dict]
    articles: list[dict]
    blocks: list[dict]
    components: list[dict]
    lang: str = config.DEFAULT_LANG

    def as_files(self) -> dict[str, Any]:
        """Course-relative path -> document, ready to write under ``src/course``."""
        return {
            "config.json": self.config,
            f"{self.lang}/course.json": self.course,
            f"{self.lang}/contentObjects.json": self.content_objects,
            f"{self.lang}/articles.json": self.articles,
            f"{self.lang}/blocks.json": self.blocks,
            f"{self.lang}/components.json": self.components,
        }


# ----------------------------------------------------------------------
# Preparation: things every page needs that the storyboard does not spell out
# ----------------------------------------------------------------------


def _nav_body(page: Page) -> str:
    if page.is_chapter:
        return config.NAV_COMPLETE_INTERACTIONS + config.NAV_CONFIDENTIAL
    return config.NAV_CONFIDENTIAL


def add_navigation(storyboard: Storyboard, report: Report) -> None:
    """Close every page with a pageNav article."""
    for page in storyboard.pages:
        article = Article(title="navigation", display_title="")
        block = Block(title="navigation", display_title="")
        block.components.append(
            Component(
                kind="pageNav",
                title=f"{page.title} Nav",
                body=_nav_body(page),
            )
        )
        article.blocks.append(block)
        page.articles.append(article)
    report.count("pageNav components", len(storyboard.pages))


def add_synthetic_pages(storyboard: Storyboard, report: Report) -> None:
    """Append pages the course needs that the storyboard never describes."""
    for spec in config.SYNTHETIC_PAGES:
        page = Page(
            slug=spec["slug"],
            title=spec["title"],
            display_title=spec["displayTitle"],
        )
        article = Article(title=spec["title"], display_title="")
        block = Block(title=spec["title"], display_title="")
        block.components.append(
            Component(
                kind="text",
                title=spec["title"],
                # Names the course that was actually built, not a baked-in one.
                body=spec["body"].format(title=as_html(storyboard.title)),
            )
        )
        article.blocks.append(block)
        page.articles.append(article)
        storyboard.pages.append(page)
        report.note(
            f"page '{spec['title']}' is not in the storyboard; generated from "
            "config.SYNTHETIC_PAGES"
        )


def build_all(
    storyboard: Storyboard,
    report: Report,
    course_dir: Path | None = None,
    lang: str = config.DEFAULT_LANG,
    print_pdf: str = "",
) -> CourseJson:
    """``course_dir`` points at the existing ``src/course`` to inherit settings from."""
    add_navigation(storyboard, report)
    add_synthetic_pages(storyboard, report)

    alloc = IdAllocator()
    content_objects: list[dict] = []
    articles: list[dict] = []
    blocks: list[dict] = []
    components: list[dict] = []

    for p_idx, page in enumerate(storyboard.pages, start=1):
        page_id = alloc.page(p_idx, page_slug(page.display_title or page.title, page.slug))
        content_objects.append(content_objects_json.build(page, page_id))

        for a_idx, article in enumerate(page.articles, start=1):
            article_id = alloc.article(p_idx, a_idx)
            articles.append(articles_json.build(article, article_id, page_id))

            for b_idx, block in enumerate(article.blocks, start=1):
                block_id = alloc.block(p_idx, a_idx, b_idx)
                blocks.append(
                    blocks_json.build(
                        block, block_id, article_id, alloc.next_tracking_id()
                    )
                )

                for c_idx, component in enumerate(block.components, start=1):
                    component_id = alloc.component(p_idx, a_idx, b_idx, c_idx)
                    ctx = Ctx(id=component_id, parent_id=block_id, report=report)
                    components.append(render(component, ctx))
                    report.count(f"component: {component.kind}")

    return CourseJson(
        lang=lang,
        config=config_json.build(report, course_dir=course_dir),
        course=course_json.build(
            storyboard,
            alloc.latest_tracking_id,
            report,
            course_dir=course_dir,
            lang=lang,
            print_pdf=print_pdf,
        ),
        content_objects=content_objects,
        articles=articles,
        blocks=blocks,
        components=components,
    )
