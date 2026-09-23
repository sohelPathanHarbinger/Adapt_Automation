"""JSON reading/writing that matches the conventions of the existing course.

The shipped ``components.json`` carries a UTF-8 BOM while its siblings do not,
and some of its text has already been corrupted into U+FFFD by a previous
round-trip through a cp1252-flavoured tool. We write plain UTF-8 without a BOM
everywhere and never emit replacement characters.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

INDENT = 2


def read_json(path: Path) -> Any:
    """Read JSON tolerating a UTF-8 BOM."""
    with path.open("r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def write_json(path: Path, data: Any) -> None:
    """Write pretty-printed UTF-8 JSON with a trailing newline, no BOM."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=INDENT, ensure_ascii=False)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
        fh.write("\n")


def deep_merge(base: Any, patch: Any) -> Any:
    """Recursively merge ``patch`` into ``base``; lists are replaced wholesale."""
    if isinstance(base, dict) and isinstance(patch, dict):
        merged = dict(base)
        for key, value in patch.items():
            merged[key] = deep_merge(merged.get(key), value) if key in merged else value
        return merged
    return patch
