"""Structural checks on the generated JSON.

Adapt fails at runtime, often silently, on a dangling ``_parentId`` or a
duplicate ``_id``. Catching those at build time is far cheaper than catching
them in the player, so every build runs these checks and reports.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from .report import Report
from .templates import PLUGIN_FOR_COMPONENT

LIST_FILES = ("contentObjects", "articles", "blocks", "components")


def validate(files: dict, report: Report, lang: str = "en") -> bool:
    """Report any structural problem. Returns True when the build is sound."""
    course = files[f"{lang}/course.json"]
    collections = {
        name: files[f"{lang}/{name}.json"] for name in LIST_FILES
    }

    ok = True
    ids: set[str] = {"course"}
    counts: Counter[str] = Counter()

    for name, collection in collections.items():
        for node in collection:
            counts[node["_id"]] += 1
            ids.add(node["_id"])

    for node_id, n in counts.items():
        if n > 1:
            report.warn(f"duplicate _id '{node_id}' appears {n} times")
            ok = False

    for name, collection in collections.items():
        for node in collection:
            if node["_parentId"] not in ids:
                report.warn(
                    f"{name}: '{node['_id']}' has _parentId "
                    f"'{node['_parentId']}' which does not exist"
                )
                ok = False

    # Every assessment must have exactly one results component pointing at it.
    declared = {
        a["_assessment"]["_id"]
        for a in collections["articles"]
        if "_assessment" in a
    }
    referenced = Counter(
        c.get("_assessmentId", "")
        for c in collections["components"]
        if c["_component"] == "assessmentResults"
    )
    for assessment_id in declared - set(referenced):
        report.warn(f"assessment '{assessment_id}' has no assessmentResults component")
        ok = False
    for assessment_id in set(referenced) - declared:
        report.warn(
            f"assessmentResults references unknown assessment '{assessment_id}'"
        )
        ok = False

    tracking = [b.get("_trackingId") for b in collections["blocks"]]
    if len(set(tracking)) != len(tracking):
        report.warn("blocks.json contains duplicate _trackingId values")
        ok = False
    latest = course.get("_latestTrackingId", 0)
    if tracking and latest < max(tracking):
        report.warn(
            f"course._latestTrackingId ({latest}) is below the highest block "
            f"_trackingId ({max(tracking)})"
        )
        ok = False

    # Questions with no correct answer would be unanswerable.
    for component in collections["components"]:
        if component["_component"] != "mcq":
            continue
        if not any(i.get("_shouldBeSelected") for i in component.get("_items", [])):
            report.warn(f"{component['_id']}: mcq has no correct option")
            ok = False

    report.count("nodes", len(ids))
    return ok


def check_plugins(files: dict, src_root: Path, report: Report, lang: str = "en") -> None:
    """Warn about a component whose Adapt plugin is not installed.

    A course referencing a component the framework does not have does not fail
    to build - it renders everything else and leaves a hole where that
    component should be, which is easy to miss until someone opens the page.
    Checking the staged tree turns that into a build-time warning.
    """
    components_dir = src_root / "src" / "components"
    if not components_dir.is_dir():
        report.note(
            f"no {components_dir} to check component plugins against - skipped"
        )
        return

    installed = {d.name for d in components_dir.iterdir() if d.is_dir()}
    used = {c.get("_component") for c in files.get(f"{lang}/components.json", [])}

    for component in sorted(filter(None, used)):
        plugin = PLUGIN_FOR_COMPONENT.get(component)
        if plugin is None:
            report.warn(
                f"component '{component}' is not one this build knows a plugin "
                "for - it may not render"
            )
        elif plugin not in installed:
            report.warn(
                f"component '{component}' needs the '{plugin}' plugin, which is "
                f"not installed in {src_root.name} - the course will not render "
                "it. Install it there, or the storyboard should not ask for it."
            )
