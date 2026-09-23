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
# Styles the parser reads. Creating them here is what makes these documents
# usable as templates: an author copies one and the styles are already there.
# --------------------------------------------------------------------------

PARAGRAPH_STYLES = [
    ("Interactivity-Heading-1", 12, True, "1F4E79"),
    ("Interactivity-Heading-2", 11, True, "2E74B5"),
    ("Interactivity-body", 11, False, None),
    ("Interactivity-Bullet-1", 11, False, None),
    ("Interactive-bullet-2", 10, False, None),
    ("Interactivity-Label", 9, False, "595959"),
    ("CYP-Question", 11, True, None),
    ("CYP - Answer", 11, False, None),
    ("CYP - TrueFalse", 11, False, None),
    ("Bullet list level 1", 11, False, None),
    ("Bullet list level 2", 10, False, None),
    ("Number bullet list 1", 11, False, None),
    ("Diagram label 1", 9, True, "595959"),
    ("footnote/diagram label", 9, True, "595959"),
    ("il Reference", 9, False, "595959"),
    ("Refrence text", 9, False, "C00000"),
]

CHARACTER_STYLES = [
    ("Glossary item Char", "1F7A3D", True),
    ("Refrence text Char", "C00000", False),
    ("Programming-Notes", "7030A0", False),
]


def ensure_styles(doc: Document) -> None:
    styles = doc.styles
    existing = {s.name for s in styles}

    for name, size, bold, colour in PARAGRAPH_STYLES:
        if name in existing:
            continue
        st = styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
        st.base_style = styles["Normal"]
        st.font.size = Pt(size)
        st.font.bold = bold
        if colour:
            st.font.color.rgb = RGBColor.from_string(colour)

    for name, colour, bold in CHARACTER_STYLES:
        if name in existing:
            continue
        st = styles.add_style(name, WD_STYLE_TYPE.CHARACTER)
        st.font.color.rgb = RGBColor.from_string(colour)
        st.font.bold = bold


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


def p(doc, style, text=""):
    """One paragraph in a named style."""
    para = doc.add_paragraph(style=style)
    if text:
        para.add_run(text)
    return para


def runs(doc, style, parts):
    """A paragraph built from (text, character-style-or-None) pairs."""
    para = doc.add_paragraph(style=style)
    for text, char in parts:
        run = para.add_run(text)
        if char:
            run.style = doc.styles[char]
    return para


def table(doc, rows, header=True):
    """Build a table. A cell given as a list holds one paragraph per entry,
    each optionally ``(style, text)`` - which is how a Key Concepts panel
    carries its topic line and then its bullets."""
    t = doc.add_table(rows=len(rows), cols=len(rows[0]))
    t.style = "Table Grid"
    for r, row in enumerate(rows):
        for c, cell in enumerate(row):
            if isinstance(cell, (list, tuple)):
                target = t.rows[r].cells[c]
                for n, entry in enumerate(cell):
                    style, text = entry if isinstance(entry, tuple) else (None, entry)
                    para = target.paragraphs[0] if n == 0 else target.add_paragraph()
                    para.text = str(text)
                    if style:
                        para.style = doc.styles[style]
                continue
            t.rows[r].cells[c].text = str(cell)
            if r == 0 and header:
                for para in t.rows[r].cells[c].paragraphs:
                    for run in para.runs:
                        run.bold = True
    doc.add_paragraph()
    return t


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

    doc.add_heading("7. What the build cannot do for you", 1)
    p(doc, "Bullet list level 1",
      "Hotgraphic pin positions - authored in base/Source and read back from there.")
    p(doc, "Bullet list level 1",
      "Key Concepts videos - the build wires up the filename and prints the script. "
      "On a Key Concepts page the script becomes an accordion instead, and the "
      "narration is published for whoever records the voiceover.")
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
