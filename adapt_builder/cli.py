"""Command line entry point.

    python build.py <course>              # build one course from Inputs/<course>/
    python build.py <course> --no-copy    # regenerate only the JSON (fast)
    python build.py <course> --apply      # also overwrite base/Source (backed up)
    python build.py <course> --dump-outline
"""

from __future__ import annotations

import argparse
import datetime as _dt
import shutil
import sys
from pathlib import Path

from . import config
from .builders import build_all
from .course_copy import DEFAULT_EXCLUDES, backup, clear_media, stage_course
from .docx_reader import parse_storyboard
from .docx_reader.images import extract_images, list_originals, write_images
from .jsonio import write_json
from .model import Storyboard
from .paths import (
    InputCourse,
    list_input_courses,
    resolve_course_tree,
    resolve_input_course,
    sanitise_name,
)
from .inherit import inherit_from_base
from .report import Report
from .validate import check_plugins, validate


def choose_course(name: str | None) -> InputCourse:
    """Resolve the course to build, or say what is available.

    One course is built per run. Naming it is only optional when ``Inputs/``
    holds exactly one, because otherwise picking for you would be a guess.
    """
    available = list_input_courses()

    if name is None:
        if len(available) == 1:
            return resolve_input_course(available[0])
        listing = "\n  ".join(available) if available else "(none found)"
        raise SystemExit(
            "error: name the course to build, e.g.\n"
            f"  python build.py {available[0] if available else '<course>'}\n\n"
            f"courses in {config.INPUTS_DIR}:\n  {listing}"
        )
    return resolve_input_course(name)


def _show(path: Path, root: Path) -> str:
    """Path as the user would recognise it: relative to the run's own root."""
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def print_pdf_name(pdf: Path | None) -> str:
    """Sanitised filename the print PDF ships under."""
    return f"{sanitise_name(pdf.stem)}.pdf" if pdf is not None else ""


def stage_print_pdf(pdf: Path | None, pdf_dir: Path, report: Report) -> None:
    """Copy the print PDF in, clearing any PDF left by the base course.

    Any other PDF in this folder belongs to the course the base source was
    authored for, and would otherwise ride along into a new module.
    """
    if pdf is None:
        return

    name = print_pdf_name(pdf)
    pdf_dir.mkdir(parents=True, exist_ok=True)
    for stale in pdf_dir.glob("*.pdf"):
        if stale.name != name:
            stale.unlink()
            report.note(f"removed inherited print PDF '{stale.name}' from the theme")
    shutil.copy2(pdf, pdf_dir / name)


def report_originals(course: InputCourse, records, report: Report) -> None:
    """Say which delivered originals replaced which storyboard figures."""
    if course.course_images is None:
        return
    used: dict[str, list[str]] = {}
    for rec in records:
        if rec.original and not rec.duplicate_of:
            used.setdefault(rec.original, []).append(rec.filename)
    report.count("figures replaced by delivered originals", sum(map(len, used.values())))
    for original, names in sorted(used.items()):
        report.note(f"original '{original}' -> {', '.join(names)}")
    for path in list_originals(course.course_images):
        if path.name not in used:
            report.warn(
                f"delivered image '{path.name}' matches no figure in the storyboard "
                "- it was not used (a newer version of a figure, or not needed?)"
            )


def overlay(source: Path, dest: Path, report: Report, what: str,
            only_existing: bool = False) -> int:
    """Copy ``source`` over ``dest`` file by file, at the same relative paths.

    ``only_existing`` restricts it to files ``dest`` already has - player
    images must replace a theme image, since nothing references a new name.
    """
    copied = 0
    for path in sorted(p for p in source.rglob("*") if p.is_file()):
        if path.name.startswith((".", "~$")):
            continue
        rel = path.relative_to(source)
        target = dest / rel
        if only_existing and not target.is_file():
            report.note(
                f"{what}: '{rel.as_posix()}' has no counterpart in the theme - skipped"
            )
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied += 1
    report.count(f"{what} files applied", copied)
    return copied


def write_course_json(files: dict, course_dir: Path) -> list[Path]:
    written = []
    for name, data in files.items():
        path = course_dir / name
        write_json(path, data)
        written.append(path)
    return written


def dump_outline(storyboard: Storyboard) -> None:
    for page in storyboard.pages:
        print(f"PAGE  {page.title}")
        for article in page.articles:
            print(f"  ART   {article.title}"
                  + (f"  [{article.assessment_id}]" if article.is_assessment else ""))
            for block in article.blocks:
                kinds = ", ".join(c.kind for c in block.components)
                print(f"    BLK {block.title or '-'}  ({kinds})")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="build.py",
        description=(
            "Build an Adapt course from its storyboard. Source material lives in "
            "Inputs/<course>/; the finished course is staged in Output/<course>/."
        ),
    )
    parser.add_argument(
        "course",
        nargs="?",
        help="course folder name under Inputs/ (or a path to it)",
    )
    parser.add_argument(
        "--out", type=Path, default=config.OUTPUT_DIR, help="output folder"
    )
    parser.add_argument(
        "--no-copy",
        action="store_true",
        help="skip staging the full course source; emit JSON and assets only",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="also write the JSON and figures into base/Source (backed up first)",
    )
    parser.add_argument(
        "--include-build",
        action="store_true",
        help="copy base/Source/build too (stale compiled output; normally skipped)",
    )
    parser.add_argument(
        "--dump-outline",
        action="store_true",
        help="print the parsed storyboard structure and exit",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    course = choose_course(args.course)
    report = Report()

    print(f"Course   {course.name}")
    print(f"Reading  {course.storyboard.name}")
    storyboard = parse_storyboard(course.storyboard, report, course.course_images)

    if args.dump_outline:
        dump_outline(storyboard)
        return 0

    # Discover the base course's layout rather than assuming it.
    base = resolve_course_tree(config.COURSE_SOURCE, config.DEFAULT_LANG)

    files = build_all(
        storyboard,
        report,
        course_dir=base.course_dir,
        lang=base.lang,
        print_pdf=print_pdf_name(course.print_pdf),
    ).as_files()

    # Positions the storyboard cannot express - hotgraphic pins - are authored
    # in base/Source and read straight back out of it.
    files = inherit_from_base(files, base.lang_dir, report)
    sound = validate(files, report, base.lang)

    out_root = args.out
    out_root.mkdir(parents=True, exist_ok=True)

    # ---- staged course source -------------------------------------------
    # One folder per course, refreshed in place. Build history lives in git
    # (branch per course), not in duplicated 200 MB folders - and keeping one
    # folder per course means its node_modules survives, so `npm install` is a
    # one-off for each.
    staged_root = out_root / course.output_name

    if args.no_copy:
        # Outside Output/ entirely, so a fast iteration run cannot leave
        # anything behind in the folder that holds the real deliverables.
        # Still per-course, so two courses cannot overwrite each other's JSON.
        json_root = config.SCRATCH_DIR / course.output_name
        display_root = config.SCRATCH_DIR
        course_dir = json_root / "course"
        figures_dir = json_root / "assets" / config.FIGURE_DIR
        if config.FIGURE_SUBDIR:
            figures_dir = figures_dir / config.FIGURE_SUBDIR
        pdf_dir = json_root / "assets" / config.PDF_SUBDIR
    else:
        excludes = set(DEFAULT_EXCLUDES)
        if args.include_build:
            excludes.discard("build")
        else:
            report.note(
                "base/Source/build was not copied - it is grunt's compiled "
                "output and still holds the previous course JSON. Run "
                "`grunt build` in the staged copy, or pass --include-build."
            )
        existed = staged_root.is_dir()
        print(
            f"{'Refreshing' if existed else 'Creating  '} "
            f"{out_root.name}/{course.output_name}  "
            f"(from {config.COURSE_SOURCE.name})"
        )
        stats = stage_course(config.COURSE_SOURCE, staged_root, excludes)
        print(f"          {stats.files} files, {stats.megabytes} MB "
              f"({stats.skipped_dirs} excluded dir(s))")

        display_root = out_root
        staged = resolve_course_tree(staged_root, base.lang)
        course_dir = staged.course_dir
        figures_dir = staged.figures_dir
        pdf_dir = staged.pdf_dir
        report.note(f"theme: {staged.theme.name}; language: {staged.lang}")

        # The base course's own media came along with the copy. Clear it before
        # this course's figures, video and PDF are written, so nothing of the
        # base's ships in someone else's module.
        cleared = clear_media(staged.theme_assets, config.KEEP_THEME_ASSETS)
        if cleared:
            report.count("inherited media file(s) cleared from the staged theme", cleared)
            print(f"          cleared {cleared} inherited media file(s) "
                  f"(kept {'/'.join(sorted(config.KEEP_THEME_ASSETS))})")

        # The course's own look: its player images and theme files, laid over
        # the base course's so a rebuild never loses them.
        if course.player_images is not None:
            player_dir = staged.theme_assets / config.PLAYER_DIR
            n = overlay(course.player_images, player_dir,
                        report, "player image", only_existing=True)
            print(f"  wrote  {n} player image(s) -> {_show(player_dir, out_root)}")
        if course.theme_overlay is not None:
            n = overlay(course.theme_overlay, staged.theme, report, "theme overlay")
            print(f"  wrote  {n} theme file(s) -> {_show(staged.theme, out_root)}")

    written = write_course_json(files, course_dir)
    for path in written:
        print(f"  wrote  {_show(path, display_root)}")

    records, _ = extract_images(course.storyboard, originals=course.course_images)
    report_originals(course, records, report)
    count = write_images(records, figures_dir)
    for name, data in storyboard.generated_images.items():
        (figures_dir / name).write_bytes(data)
        count += 1
    print(f"  wrote  {count} figure(s) -> {_show(figures_dir, display_root)}")
    report.count("figures extracted", count)

    stage_print_pdf(course.print_pdf, pdf_dir, report)
    if course.print_pdf is not None:
        print(f"  wrote  {print_pdf_name(course.print_pdf)} "
              f"-> {_show(pdf_dir, display_root)}")

    # The report belongs with the course it describes, so Output/ holds one
    # folder per course and nothing else.
    # Now that the course is staged, its plugins can be checked - a component
    # whose plugin is missing renders as a hole in the page, not an error.
    check_plugins(files, config.COURSE_SOURCE if args.no_copy else staged_root,
                  report, base.lang)

    report_path = (json_root if args.no_copy else staged_root) / "report.md"
    report.write(report_path)

    # ---- optional in-place apply ----------------------------------------
    if args.apply and not sound:
        print()
        print("Refusing --apply: the build has structural errors (see the report).")
        print(f"The staged copy in {out_root.name}/ is still available to inspect.")
        return 1

    if args.apply:
        label = _dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        snapshot = backup(base.course_dir, config.BACKUP_DIR, label)
        print(f"Backup   {snapshot}")
        write_course_json(files, base.course_dir)
        write_images(records, base.figures_dir)
        stage_print_pdf(course.print_pdf, base.pdf_dir, report)
        print(f"Applied  -> {base.course_dir}")

    print()
    print(f"Report   {report_path}  "
          f"({len(report.warnings)} warning(s), {len(report.notes)} note(s))")
    for warning in report.warnings[:10]:
        print(f"  ! {warning}")
    if len(report.warnings) > 10:
        print(f"  ... {len(report.warnings) - 10} more in {report_path.name}")

    return 0 if sound else 1


if __name__ == "__main__":
    sys.exit(main())
