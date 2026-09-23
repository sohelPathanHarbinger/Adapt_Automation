"""Build report: everything the automation could not decide on its own."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Report:
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    stats: Counter = field(default_factory=Counter)
    #: Instructions the storyboard addressed to the programmer, stripped out of
    #: the copy. Someone still has to act on each one.
    programming_notes: list[str] = field(default_factory=list)
    #: Narration / on-screen-text specs for videos this build cannot produce.
    scripts: list[dict[str, str]] = field(default_factory=list)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def note(self, message: str) -> None:
        self.notes.append(message)

    def count(self, key: str, n: int = 1) -> None:
        self.stats[key] += n

    def render(self) -> str:
        lines = ["# Storyboard build report", ""]

        lines.append("## Structure")
        lines.append("")
        for key in sorted(self.stats):
            lines.append(f"- {key}: {self.stats[key]}")
        lines.append("")

        lines.append(f"## Warnings ({len(self.warnings)})")
        lines.append("")
        if self.warnings:
            lines.extend(f"- {w}" for w in self.warnings)
        else:
            lines.append("None.")
        lines.append("")

        lines.append(f"## Notes ({len(self.notes)})")
        lines.append("")
        if self.notes:
            lines.extend(f"- {n}" for n in self.notes)
        else:
            lines.append("None.")
        lines.append("")

        if self.programming_notes:
            lines.append(f"## Programming notes ({len(self.programming_notes)})")
            lines.append("")
            lines.append(
                "Instructions the storyboard left for the programmer. They were "
                "removed from the shipped copy; each one still needs doing."
            )
            lines.append("")
            lines.extend(f"- {n}" for n in self.programming_notes)
            lines.append("")

        if self.scripts:
            lines.append(f"## Key Concepts videos ({len(self.scripts)})")
            lines.append("")
            lines.append(
                "The storyboard specifies these as narration plus on-screen "
                "text rather than shipping a video. Each media component is "
                "wired to the filename its video must be delivered under; drop "
                "the file into the theme's `assets/videos/` to complete it."
            )
            lines.append("")
            for script in self.scripts:
                lines.append(f"### {script.get('title') or 'Untitled'}")
                lines.append("")
                lines.append(f"- page: {script.get('page', '')}")
                if script.get("src"):
                    lines.append(f"- expected file: `{script['src']}`")
                else:
                    lines.append(
                        "- built as the page's Key Concepts accordion; the "
                        "narration below is the voiceover script"
                    )
                lines.append("")
                lines.append("**On screen text**")
                lines.append("")
                lines.append(script.get("onscreen") or "_none given_")
                lines.append("")
                lines.append("**Narration**")
                lines.append("")
                lines.append(script.get("narration") or "_none given_")
                lines.append("")

        return "\n".join(lines)

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.render(), encoding="utf-8", newline="\n")
