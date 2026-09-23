"""Generate the storyboard authoring guide and the reference storyboard.

Both are written with the exact Word styles the parser reads, so the reference
storyboard is not a picture of the conventions - it is a course that builds.
"""

from __future__ import annotations

import sys
from pathlib import Path

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

sys.path.insert(0, "d:/Work/Illuminate/Adapt/01_Automation")
from adapt_builder import config  # noqa: E402

ROOT = Path("d:/Work/Illuminate/Adapt/01_Automation")
DEST = ROOT / "Documentation" / "Template_Reference"
GUIDE_DIR = DEST / "guide"

# --------------------------------------------------------------------------
# Styles the parser reads and the small builders both documents use live in
# tools/storyboard_docx.py, so this guide and the base storyboard can never
# describe different conventions.
# --------------------------------------------------------------------------

sys.path.insert(0, str(ROOT / "tools"))
from storyboard_docx import ensure_styles, p, runs, table  # noqa: E402


def _sample_image() -> Path:
    """A small placeholder PNG, built here so the generator needs no assets."""
    import struct
    import zlib

    width = height = 64

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    # A plain mid-blue square: one filter byte then RGB triples per row.
    raw = b"".join(
        b"\x00" + bytes([0x2E, 0x74, 0xB5]) * width for _ in range(height)
    )
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )
    out = Path(__file__).with_name("_sample_figure.png")
    out.write_bytes(png)
    return out


# ==========================================================================
# 1. The authoring guide
# ==========================================================================


def build_guide(path: Path) -> None:
    doc = Document()
    ensure_styles(doc)

    doc.add_heading("Storyboard Authoring Guide", 0)
    para = doc.add_paragraph()
    para.add_run(
        "How to style a storyboard so the automation can build it. Every rule "
        "here is enforced by Word styles, not by wording - the parser reads "
        "styles, so a paragraph in the wrong style lands in the wrong place no "
        "matter what it says."
    ).italic = True
    doc.add_paragraph(
        "The companion file, Template Reference Storyboard.docx, is a working "
        "example of everything below. It builds; use it to check a change to "
        "the automation, or copy from it when authoring."
    )

    doc.add_heading("1. Structure", 1)
    doc.add_paragraph(
        "Four paragraph styles carry the whole shape of the course:"
    )
    table(doc, [
        ["Word style", "Becomes", "Notes"],
        ["Heading 1", "Page", "One per page. 'Glossary' and 'References' are special."],
        ["Heading 2", "Article", "'Check Your Progress' and 'Answers' are special."],
        ["Heading 3 / 4 / 5", "Block", "A block groups components under a heading."],
        ["Normal", "Body copy", "Collected into a text component."],
    ])

    doc.add_heading("2. Body copy", 1)
    table(doc, [
        ["Word style", "Becomes"],
        ["Normal, List Paragraph", "A paragraph"],
        ["Bullet list level 1", "A bulleted item"],
        ["Bullet list level 2", "A nested bulleted item"],
        ["Number bullet list 1", "A numbered item; reference entries on the References page"],
        ["Diagram label 1 / footnote/diagram label", "A caption - on the figure above, or the table below"],
        ["il Reference", "An entry on the References page"],
        ["Refrence text", "A citation paragraph - removed entirely"],
    ])

    doc.add_heading("3. Character styles", 1)
    doc.add_paragraph(
        "These apply to selected words inside a paragraph, not to the whole "
        "paragraph."
    )
    table(doc, [
        ["Character style", "Effect"],
        ["Glossary item Char", "Marks a glossary term; the definition comes from the Glossary table"],
        ["Refrence text Char", "A medical/legal citation - removed, never shown to the learner"],
        ["Programming-Notes", "An instruction to the course builder - removed, listed in the report"],
        ["Bold", "Renders as bold"],
    ])

    doc.add_heading("4. Interactivities", 1)
    doc.add_paragraph(
        "Start one with a paragraph styled Interactivity-Heading-1. Two label "
        "forms are accepted:"
    )
    p(doc, "Interactivity-Bullet-1", "Interactivity: Accordion   - the type after the colon")
    p(doc, "Interactivity-Bullet-1", "Accordion: Learning Objectives   - the type first, its own heading after")
    p(doc, "Interactivity-Bullet-1", "End Interactivity: Accordion   - closes the open one")
    doc.add_paragraph(
        "Inside it, Interactivity-Heading-2 starts each panel, and "
        "Interactivity-body / Interactivity-Bullet-1 carry that panel's copy."
    )

    doc.add_heading("Every type the automation supports", 2)
    rows = [["Type the storyboard to write", "Adapt component"]]
    seen = {}
    for label, kind in sorted(config.INTERACTIVITY_MAP.items()):
        seen.setdefault(kind, []).append(label)
    for kind, labels in sorted(seen.items()):
        rows.append([", ".join(sorted(labels)), kind])
    table(doc, rows)

    doc.add_heading("5. Questions", 1)
    table(doc, [
        ["Word style", "Becomes"],
        ["CYP-Question", "A question stem (under a 'Check Your Progress' Heading 2)"],
        ["CYP - Answer", "One answer option"],
        ["CYP - TrueFalse", "A True or False option"],
    ])
    doc.add_paragraph(
        "Put the answer key under a Heading 2 called 'Answers', one line per "
        "question, in the same order: a letter (D), several letters (B, C), or "
        "True / False. A trailing explanation is ignored, so 'False. INGREZZA "
        "is...' works."
    )
    doc.add_paragraph(
        "Bold the correct option as well. The build compares the two and warns "
        "when they disagree - that cross-check is the point of the QC pass."
    )

    doc.add_heading("6. Tables", 1)
    doc.add_paragraph("A table becomes one of five things, decided by its content:")
    table(doc, [
        ["Kind", "Recognised by", "Becomes"],
        ["Glossary", "On the Glossary page", "Glossary table plus every inline definition"],
        ["Narration", "A 'Narration | On Screen Text' header row", "A media (video) component plus its script in the report - or, on a Key Concepts page, that page's Key Concepts accordion"],
        ["Matching", "Under Check Your Progress, a column of A.-lettered stems", "A matching component"],
        ["Grid", "Under Check Your Progress, 2+ columns holding only X", "A selectchoice component"],
        ["Data", "Anything else", "An HTML table in the copy that introduces it"],
    ])

    doc.add_heading("7. Videos", 1)
    doc.add_paragraph(
        "A narration table becomes a video component. Name the file on a line "
        "of its own above the table, styled Programming-Note:"
    )
    p(doc, "Bullet list level 1", "Video: kc_chapter1.mp4")
    p(doc, "Bullet list level 1", "Video: kc_chapter1.mp4, Poster: kc_chapter1-cover.png")
    doc.add_paragraph(
        "On a Key Concepts page this is also how the chunk is asked for as a "
        "video: name a file and it becomes one; name none and it stays an "
        "accordion. The file need not exist yet - the component is wired to it "
        "and the report says the file is still to come."
    )
    doc.add_paragraph(
        "Deliver the video, its captions and its poster in "
        "Inputs/<course>/assets/videos/ - captions as vtt/<name>.vtt. The build "
        "copies them in, and reports anything named but missing, or delivered "
        "but unused. Without a poster it uses <name>-poster.png, then the "
        "video's first frame where ffmpeg is available, then the theme default."
    )

    doc.add_heading("8. What the build cannot do for you", 1)
    p(doc, "Bullet list level 1",
      "Hotgraphic pin positions - authored in base/Source and read back from there.")
    p(doc, "Bullet list level 1",
      "Recording the Key Concepts voiceover - the build wires up the filename and "
      "publishes the script. A Key Concepts chunk is an accordion unless the "
      "storyboard names a video for it (see 7).")
    p(doc, "Bullet list level 1",
      "Images inside gmcq / graphic slider options - the paths are left empty.")

    doc.add_paragraph()
    doc.add_paragraph(
        "After every build, read Output/<course>/report.md. It lists exactly "
        "what needed a human decision."
    ).italic = True

    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))
    print("wrote", path)


# ==========================================================================
# 2. The reference storyboard - minimal content, every template
# ==========================================================================


def build_storyboard(path: Path) -> None:
    doc = Document()
    ensure_styles(doc)

    doc.core_properties.title = "Template Reference Module"

    # ---- Chapter 1: content components -----------------------------------
    doc.add_heading("Chapter 1: Content Components", 1)

    doc.add_heading("Learning Objectives", 2)
    p(doc, "Interactivity-Heading-1", "Accordion: Learning Objectives")
    p(doc, "Interactivity-Heading-2", "Upon completion of this chapter, learners will be able to:")
    p(doc, "Interactivity-Bullet-1", "Recognise every component this automation can build.")
    p(doc, "Interactivity-Bullet-1", "Author a storyboard that exercises each of them.")

    doc.add_heading("Section 1.1: Text and Lists", 2)
    doc.add_heading("Body copy", 3)
    runs(doc, "Normal", [
        ("This paragraph becomes a text component. The term ", None),
        ("tetramer", "Glossary item Char"),
        (" is marked as a glossary item, so it becomes a popup. ", None),
        ("[Reference PI p1/A]", "Refrence text Char"),
        (" This citation is removed before the learner sees it.", None),
    ])
    p(doc, "Bullet list level 1", "A level one bullet.")
    p(doc, "Bullet list level 2", "A level two bullet, nested inside it.")
    p(doc, "Normal", "A numbered list follows:")
    p(doc, "Number bullet list 1", "First numbered item.")
    p(doc, "Number bullet list 1", "Second numbered item.")

    doc.add_heading("A data table", 3)
    p(doc, "Normal", "The caption below names the table, so it heads it.")
    p(doc, "Diagram label 1", "Table 1-1: A Simple Data Table")
    table(doc, [
        ["Parameter", "Value A", "Value B"],
        ["First measure", "10", "20"],
        ["Second measure", "30", "40"],
    ])

    doc.add_heading("A figure", 3)
    doc.add_picture(str(_sample_image()), width=Inches(2.2))
    p(doc, "Diagram label 1", "Figure 1-1: A Sample Figure")

    doc.add_heading("Section 1.2: Callout", 2)
    p(doc, "Normal", "Body copy that the callout below annotates.")
    p(doc, "Interactivity-Heading-1", "Interactivity: Callout")
    p(doc, "Interactivity-Heading-2", "ZOOM IN: A Closer Look")
    p(doc, "Interactivity-body", "A callout becomes a hint attached to the component above it.")

    # ---- Chapter 2: interactivities ---------------------------------------
    doc.add_heading("Chapter 2: Interactivities", 1)

    doc.add_heading("Section 2.1: Accordion and Tabs", 2)
    p(doc, "Interactivity-Heading-1", "Interactivity: Accordion")
    p(doc, "Interactivity-Heading-2", "Accordion 1: First Panel")
    p(doc, "Interactivity-Bullet-1", "Copy for the first accordion panel.")
    p(doc, "Interactivity-Heading-2", "Accordion 2: Second Panel")
    p(doc, "Interactivity-Bullet-1", "Copy for the second accordion panel.")

    p(doc, "Interactivity-Heading-1", "Interactivity: Vertical Tabs")
    p(doc, "Interactivity-Heading-2", "Tab 1: First Tab")
    p(doc, "Interactivity-body", "Copy for the first tab.")
    p(doc, "Interactivity-Heading-2", "Tab 2: Second Tab")
    p(doc, "Interactivity-body", "Copy for the second tab.")

    doc.add_heading("Section 2.2: Narrative and Hot Spots", 2)
    p(doc, "Interactivity-Heading-1", "Interactivity: Narrative")
    p(doc, "Interactivity-Heading-2", "Step 1: The Beginning")
    p(doc, "Interactivity-body", "Copy for the first narrative panel.")
    p(doc, "Interactivity-Heading-2", "Step 2: The Middle")
    p(doc, "Interactivity-body", "Copy for the second narrative panel.")

    p(doc, "Interactivity-Heading-1", "Interactivity: Hot Spots")
    p(doc, "Interactivity-Heading-2", "Hot spot 1: First Pin")
    p(doc, "Interactivity-body", "Copy shown when the first pin is opened.")
    p(doc, "Interactivity-Heading-2", "Hot spot 2: Second Pin")
    p(doc, "Interactivity-body", "Copy shown when the second pin is opened.")
    p(doc, "Interactivity-Label", "Source: reference storyboard")

    doc.add_heading("Section 2.3: Popups, Table and Sliders", 2)
    p(doc, "Interactivity-Heading-1", "Interactivity: Text with Popups")
    p(doc, "Interactivity-Heading-2", "First popup")
    p(doc, "Interactivity-body", "What the first popup shows.")
    p(doc, "Interactivity-Heading-2", "Second popup")
    p(doc, "Interactivity-body", "What the second popup shows.")

    p(doc, "Interactivity-Heading-1", "Interactivity: Spacer")
    p(doc, "Interactivity-body", "A blank component is pure spacing and holds no copy.")

    p(doc, "Interactivity-Heading-1", "Interactivity: Graphic MCQ")
    p(doc, "Interactivity-Heading-2", "The first picture option.")
    para = doc.add_paragraph(style="Interactivity-Heading-2")
    para.add_run("The second picture option, bolded because it is correct.").bold = True

    p(doc, "Interactivity-Heading-1", "Interactivity: Graphic Slider")
    p(doc, "Interactivity-Heading-2", "Stop 1: Start")
    p(doc, "Interactivity-body", "The image shown at the first stop.")
    p(doc, "Interactivity-Heading-2", "Stop 2: End")
    p(doc, "Interactivity-body", "The image shown at the last stop.")

    doc.add_heading("Section 2.4: Slider, Text Input and Table", 2)
    p(doc, "Interactivity-Heading-1", "Interactivity: Slider")
    p(doc, "Interactivity-body", "How confident are you about this material?")
    p(doc, "Interactivity-Heading-2", "Scale: 1 to 10")
    p(doc, "Interactivity-Heading-2", "Answer: 7")
    p(doc, "Interactivity-Heading-2", "Labels: not at all, completely")

    p(doc, "Interactivity-Heading-1", "Interactivity: Text Input")
    p(doc, "Interactivity-body", "Type the abbreviation for the protein described above.")
    p(doc, "Interactivity-Heading-2", "TTR / transthyretin")

    p(doc, "Interactivity-Heading-1", "Interactivity: Table")
    table(doc, [
        ["Column A", "Column B"],
        ["First value", "Second value"],
        ["Third value", "Fourth value"],
    ])

    # ---- Chapter 3: questions ---------------------------------------------
    doc.add_heading("Chapter 3: Questions", 1)

    doc.add_heading("Section 3.1: Narration", 2)
    p(doc, "Normal", "The table below is a video script, not learner copy.")
    p(doc, "Programming-Note", "Video: section-3-1.mp4, Poster: section-3-1-poster.png")
    table(doc, [
        ["Narration for Section 3.1 Presentation", "On Screen Text"],
        ["This is what the voiceover says.", "This is what appears on screen."],
    ])

    # Key Concepts authored twice: the print copy is skipped, and the
    # programming copy becomes the page's Key Concepts accordion.
    doc.add_heading("Key Concepts (For Print)", 2)
    p(doc, "Normal", "This copy is for the print PDF only and is not built.")

    doc.add_heading("Key Concepts (For Programming)", 2)
    table(doc, [
        ["Narration for KCs Presented by Avatar", "On Screen Text"],
        ["What the avatar says about the first topic.",
         ["First Topic",
          ("Bullet list level 1", "A point about the first topic."),
          ("Bullet list level 1", "Another point.")]],
        ["What the avatar says about the second topic.",
         ["Second Topic",
          ("Bullet list level 1", "A point about the second topic.")]],
    ])

    doc.add_heading("Check Your Progress", 2)
    p(doc, "CYP-Question", "Which of the following is a multiple choice question?")
    p(doc, "CYP - Answer", "The first option.")
    para = doc.add_paragraph(style="CYP - Answer")
    para.add_run("The second option, bolded because it is correct.").bold = True
    p(doc, "CYP - Answer", "The third option.")

    p(doc, "CYP-Question", "True or false? A True/False question uses the CYP - TrueFalse style.")
    p(doc, "CYP - TrueFalse", "True")
    p(doc, "CYP - TrueFalse", "False")

    p(doc, "CYP-Question", "Match each item with its description.")
    table(doc, [
        ["", "Alpha", "", "A. The description that belongs to Beta."],
        ["", "Beta", "", "B. The description that belongs to Alpha."],
    ], header=False)

    p(doc, "CYP-Question", "Mark whether each statement is an inclusion or an exclusion.")
    table(doc, [
        ["Inclusion", "Exclusion", ""],
        ["X", "", "A statement that is an inclusion."],
        ["", "X", "A statement that is an exclusion."],
    ])

    doc.add_heading("Answers", 2)
    p(doc, "CYP-Question", "B")
    p(doc, "CYP-Question", "True")
    table(doc, [
        ["B", "Alpha", "", "A. The description that belongs to Beta."],
        ["A", "Beta", "", "B. The description that belongs to Alpha."],
    ], header=False)
    p(doc, "CYP-Question", "Inclusion, exclusion")

    # ---- References and Glossary -------------------------------------------
    doc.add_heading("References", 1)
    p(doc, "il Reference", "Author A. A reference entry. Journal Name. 2025;1(1):1-10.")
    p(doc, "il Reference", "Author B. Another reference entry. Journal Name. 2024;2(2):20-30.")

    doc.add_heading("Glossary", 1)
    table(doc, [
        ["tetramer", "a protein made up of four subunits"],
        ["monomer", "a single molecule that can bind to others to form a polymer"],
    ], header=False)

    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))
    print("wrote", path)


if __name__ == "__main__":
    build_guide(GUIDE_DIR / "Storyboard Authoring Guide.docx")
    build_storyboard(DEST / "Template Reference Storyboard.docx")
