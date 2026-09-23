"""Deterministic _id generation.

IDs encode the node's position in the storyboard, so the same document always
produces the same IDs and a diff between two builds is readable:

    co-02-ch1              page
      a-02-03              article 3 of page 2
        b-02-03-01         block 1 of that article
          c-02-03-01-01    component 1 of that block
"""

from __future__ import annotations

import re


def page_slug(title: str, fallback: str) -> str:
    """Short, stable, human-readable page key."""
    chapter = re.match(r"^\s*chapter\s+(\d+)", title, re.I)
    if chapter:
        return f"ch{chapter.group(1)}"
    words = re.sub(r"[^A-Za-z0-9\s]", " ", title).split()
    slug = "-".join(w.lower() for w in words[:3])
    return slug or fallback


class IdAllocator:
    """Hands out IDs and sequential tracking IDs for one build."""

    def __init__(self) -> None:
        self._tracking = 0
        self._seen: set[str] = set()

    def _unique(self, candidate: str) -> str:
        if candidate not in self._seen:
            self._seen.add(candidate)
            return candidate
        n = 2
        while f"{candidate}-{n}" in self._seen:
            n += 1
        final = f"{candidate}-{n}"
        self._seen.add(final)
        return final

    def page(self, index: int, slug: str) -> str:
        return self._unique(f"co-{index:02d}-{slug}")

    def article(self, page_index: int, index: int) -> str:
        return self._unique(f"a-{page_index:02d}-{index:02d}")

    def block(self, page_index: int, article_index: int, index: int) -> str:
        return self._unique(f"b-{page_index:02d}-{article_index:02d}-{index:02d}")

    def component(
        self, page_index: int, article_index: int, block_index: int, index: int
    ) -> str:
        return self._unique(
            f"c-{page_index:02d}-{article_index:02d}-{block_index:02d}-{index:02d}"
        )

    def next_tracking_id(self) -> int:
        self._tracking += 1
        return self._tracking

    @property
    def latest_tracking_id(self) -> int:
        return self._tracking
