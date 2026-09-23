"""Carry hand-set values across from ``base/Source`` into a fresh build.

Some things a course needs are not in the storyboard and never will be -
hotgraphic pin coordinates are the standing example, because a storyboard has
no way to say "put this pin 22% from the left". They *are* in ``base/Source``,
which is the authored course someone has already positioned by hand.

So they are read from there rather than restated anywhere else. ``base/Source``
is the single place a hand-set value lives; there is no second copy to keep in
step with it.

The one thing that makes this less than trivial is that IDs do not survive:
this build regenerates them from the storyboard's structure, so the authored
``c-125`` is this build's ``c-03-03-01-02``. Components are therefore matched by
kind and position, and their items by title - never by ``_id``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .jsonio import read_json
from .report import Report

#: Per-item keys carried across. Deliberately a short list: these are the
#: values a storyboard cannot express, not a general patching mechanism.
PIN_KEYS = ("_top", "_left")


def _norm(text: Any) -> str:
    """Compare titles on their words alone, ignoring markup and punctuation."""
    if not isinstance(text, str):
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _by_component(components: list[dict], kind: str) -> list[dict]:
    return [c for c in components if c.get("_component") == kind]


def inherit_from_base(
    files: dict[str, Any], base_lang_dir: Path, report: Report
) -> dict[str, Any]:
    """Copy hand-set positions from the authored course into ``files``.

    Returns ``files``, changed in place. A missing or unreadable base course is
    not an error: the build still produces a working course, just with the
    placeholder pin positions the report already warns about.
    """
    name = next((n for n in files if Path(n).name == "components.json"), None)
    if name is None:
        return files

    base_path = base_lang_dir / "components.json"
    if not base_path.is_file():
        report.note(
            f"no {base_path.name} in base/Source - hand-set positions could not "
            "be inherited"
        )
        return files

    try:
        base_components = read_json(base_path)
    except (OSError, ValueError) as exc:
        report.warn(f"base/Source components.json could not be read ({exc})")
        return files
    if not isinstance(base_components, list):
        report.warn("base/Source components.json is not a list - ignored")
        return files

    _inherit_hotgraphic_pins(files[name], base_components, report)
    return files


def _inherit_hotgraphic_pins(
    generated: list[dict], base_components: list[dict], report: Report
) -> None:
    """Give each generated hotgraphic the pin positions authored in base/Source.

    Hotgraphics are paired in document order, which is the only correspondence
    available once IDs have been regenerated - but the pairing has to be earned
    by at least one hotspot title matching, because ``base/Source`` holds one
    specific course and another course's coordinates would be meaningless on a
    different image. Within a confirmed pair, items are matched on their title
    so that reordering a hotspot moves its pin with it; a hotspot that was
    reworded falls back to its position.
    """
    gen = _by_component(generated, "hotgraphic")
    base = _by_component(base_components, "hotgraphic")
    if not gen:
        return

    # "_pinSource" marks pins the build placed itself. It is build-internal, so
    # it comes off every component here, whatever else happens.
    computed_ids = {
        str(c.get("_id")) for c in gen if c.pop("_pinSource", None) == "panels"
    }

    if not base:
        report.note(
            "base/Source has no hotgraphic to inherit pin positions from - "
            "this build's pins are placeholders"
        )
        return

    inherited = 0
    #: Components this pass has said something specific about. The template's
    #: generic placeholder advice is then redundant for them.
    explained: set[str] = set()

    for index, component in enumerate(gen):
        # Pins the build placed itself are right unless base/Source says
        # otherwise; they are not placeholders worth a warning.
        computed = str(component.get("_id")) in computed_ids
        if computed:
            explained.add(str(component.get("_id")))
        if index >= len(base):
            if computed:
                continue
            report.warn(
                f"{component.get('_id')}: base/Source has only {len(base)} "
                "hotgraphic(s), so this one's pins are placeholders - set "
                "_top/_left on it in base/Source"
            )
            explained.add(str(component.get("_id")))
            continue

        base_items = base[index].get("_items", [])
        lookup = {
            _norm(item.get("title")): item
            for item in base_items
            if _norm(item.get("title"))
        }
        items = component.get("_items", [])

        # A pin position only means anything on the image it was placed on, and
        # base/Source holds one specific course. So the pairing has to be
        # earned: unless some hotspot titles actually match, this is a
        # different course's hotgraphic and its coordinates are not ours.
        matched = [i for i in items if _norm(i.get("title")) in lookup]
        if not matched and computed:
            continue
        if not matched:
            report.warn(
                f"{component.get('_id')}: no hotspot titles match the hotgraphic "
                "in base/Source, so its pins are placeholders - position them in "
                "base/Source, or accept the defaults"
            )
            explained.add(str(component.get("_id")))
            continue

        explained.add(str(component.get("_id")))
        for position, item in enumerate(items):
            source = lookup.get(_norm(item.get("title")))
            if source is None and position < len(base_items):
                # This hotspot was reworded, but its siblings identify the
                # hotgraphic, so its position is still the right one to take.
                source = base_items[position]
            if source is None or not all(key in source for key in PIN_KEYS):
                continue
            for key in PIN_KEYS:
                item[key] = source[key]
            inherited += 1

    if inherited:
        report.count("pin positions inherited from base/Source", inherited)

    # The template's placeholder advice was written while the component was
    # built. For every hotgraphic this pass has since resolved or explained, it
    # is now either wrong or a duplicate of a more specific message.
    if explained:
        report.warnings = [
            w
            for w in report.warnings
            if not (
                "hotgraphic pin coordinates" in w
                and any(w.startswith(f"{cid}:") for cid in explained)
            )
        ]
