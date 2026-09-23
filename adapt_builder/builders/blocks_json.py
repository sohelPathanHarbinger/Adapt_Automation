"""blocks.json - one record per block, carrying the SCORM tracking id."""

from __future__ import annotations

from ..model import Block


def build(block: Block, block_id: str, article_id: str, tracking_id: int) -> dict:
    return {
        "_id": block_id,
        "_parentId": article_id,
        "_type": "block",
        "_classes": "",
        "title": block.title,
        "displayTitle": block.display_title,
        "body": "",
        "instruction": "",
        "_trackingId": tracking_id,
    }
