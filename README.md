# Storyboard → Adapt course build

Reads a course's storyboard from `Inputs/<course>/`, regenerates the whole
`src/course` JSON set from it, and stages a complete, buildable copy of the
course in `Output/<course>/`.

```bash
pip install -r requirements.txt          # once

python build.py <course>                 # ← the normal command
```

`<course>` is a folder name under `Inputs/`. **One course is built per run** —
several can sit in `Inputs/` at once, and you name the one you want. With
exactly one course there, the name can be omitted. Other modes:

```bash
python build.py <course> --dump-outline  # print the parsed structure, write nothing
python build.py <course> --no-copy       # regenerate only the JSON (fast iteration)
python build.py <course> --apply         # also overwrite base/Source (backed up first)
python build.py --help
```

After a build, read **`Output/<course>/report.md`** first. It lists everything the
automation could not decide on its own. `build.py` exits non-zero if validation
found a structural problem, so it drops straight into CI if you ever want that.

## Folders

| Folder | What it is |
| --- | --- |
| `Inputs/<course>/` | one folder per course — its storyboard, print PDF and assets. **Not committed**: client material stays local |
| `base/Source/` | the authored Adapt course every build starts from — one sample of every template the automation emits; **never written to** unless you pass `--apply` |
| `base/Inputs/` | a reference input folder, and the storyboard `base/Source` was built from: copy its layout to start `Inputs/<course>/`. Never built as a live course |
| `Documentation/` | the User Guide, and `Template_Reference/` — the storyboard that exercises every component |
| `Output/<course>/` | one staged, buildable course per input course |
| `adapt_builder/` | the automation |

## Input layout

One folder per course. The **folder name is the course name** — it is what you
pass on the command line and what the output folder is called.

```
Inputs/
  BBIO_1468_Attruby_Product_Mod_D7v9_programming_QC/
    BBIO 1468 Attruby Product Mod D7v9_programming QC.docx   the storyboard
    BBIO 1468 Attruby Product Mod D7v9-Print_v2.pdf          Resources download
    assets/images/Course/        hi-res originals of the storyboard's figures
    assets/images/Player/        theme GUI images, laid out like the theme's assets/GUI
    theme/                       files laid over src/theme/<theme>/ (the course palette)
```

All three are optional:

- **`assets/images/Course/`**: each delivered original replaces the embedded
  figure it *looks like*, so names don't matter ("Figure 1-2A.jpg",
  "iStock-123.jpg"). Matching uses a coarse visual fingerprint plus aspect
  ratio (`config.IMAGE_MATCH_THRESHOLD`). The figure keeps its build name, and
  files over `config.IMAGE_MAX_SIDE` px are scaled down. The report lists every
  replacement, plus each original that matched nothing. Needs Pillow.
  Art redrawn in new branding looks nothing like the figure it replaces, so a
  delivered file whose **name states the figure** pairs with it regardless:
  `... (storyboard Figure 2-1 ...).png` replaces the storyboard's "Figure 2-1".
- **`assets/images/Player/`**: overwrites the theme file at the same relative
  path under `assets/GUI`. A file with no counterpart there is reported and
  skipped. To start one, copy `base/Source`'s `assets/GUI` and swap files as
  final art arrives.
- **`theme/`**: copied over the staged theme. Grunt compiles all theme LESS as
  one unit in path order, so `theme/less/zz-course-theme.less` sorts last and
  can redefine palette variables (`@primary`, ...) without touching
  `base/Source`.

The `.docx` and `.pdf` inside can be named anything — the newest `.docx` is the
storyboard, and the first `.pdf` becomes the Resources drawer download. Add a
second course by adding a second folder; nothing in the automation changes. A
folder without a `.docx` is not a course and is passed over.

### Recolouring the player art

Until the final theme images arrive, `base/Source`'s player art can be moved
onto a course's palette:

```bash
python tools/recolour_gui.py base/Source/src/theme/<theme>/assets/GUI        "Inputs/<course>/assets/images/Player" background.png,logo.png
```

It maps by hue - the normal state, the hover state and the panel tints each
become their counterpart in the new palette - and flattens each one to a solid
colour, because the design has no gradients in its interface. Anti-aliased
edges keep their blend, so nothing goes jagged. The third argument lists files
to copy untouched (the logo and background come from the Figma file instead).

## Output layout

```
Output/
  BBIO_1468_Attruby_Product_Mod_D7v9_programming_QC/         ← the course name
    src/course/config.json
    src/course/en/{course,contentObjects,articles,blocks,components}.json
    src/theme/<theme>/assets/images/           extracted figures (course art)
    src/theme/<theme>/assets/GUI/              player art: background, logo, nav, callout icons
    src/theme/<theme>/assets/pdf/              the print PDF
    Gruntfile.js, package.json, ...            ready for grunt
    report.md                                  ← read this first
```

Course figures go to `assets/images/` because they are the course's own
artwork; `assets/GUI/` is player art, and a course's `assets/images/Player/`
overlay lands there. Both are set in `config.py` (`FIGURE_DIR`, `PLAYER_DIR`).

A staged course starts as a copy of `base/Source`, media and all, so the
**base's own media is cleared** before this course's figures, video and PDF are
written - every folder under `assets/` except the player art
(`config.KEEP_THEME_ASSETS`). A module therefore ships only what its storyboard
produced and what it delivered itself. The report says how many files went.

`Output/` holds **one folder per course and nothing else** — the report lives
with the course it describes, so it always travels with the build it came from.

Nothing is hard-coded: the theme folder under `src/theme/` and the language
folder under `src/course/` are both discovered from `base/Source`, so a
different theme or a non-`en` course needs no code change.

### One folder per course, refreshed in place

Rebuilding a course **refreshes its folder**: stale files are cleared, so what
you get is exactly what this build produced. A different course gets its own
folder, so several can live in `Output/` at once and building one never
disturbs another.

`node_modules/`, `.git/` and `build/` inside the staged folder are **kept**
across refreshes — so `npm install` is a one-off per course, and the folder can
be a git working copy without the build stamping on it.

Build history is not kept as duplicated folders. Of a 202 MB staged course only
~10 MB is generated (300 KB of JSON, 4.8 MB of figures, the print PDF); the
rest is an identical copy of `base/Source`, and each copy would need its own
`npm install` to be usable. History belongs in git instead — a branch per
course, where `git log -- src/course/` gives real diffs. Old builds stay
reproducible because the storyboard that produced them is archived in
`Inputs/<course>/`.

`--no-copy` writes to `_scratch/<course>/` — outside `Output/`, so fast
iteration never leaves anything behind among the real deliverables.

To run the staged course:

```bash
cd Output/<course>
npm install        # first time only; it survives later rebuilds
grunt build        # or: grunt dev
```

`node_modules/`, `.git/` and `build/` are never copied *from* `base/Source`.
`build/` is skipped because it is grunt's compiled output and still contains
the *previous* course JSON — pass `--include-build` if you want it anyway.

`--apply` snapshots `base/Source/src/course` into `_backups/<timestamp>/`
before overwriting, and refuses to run at all if validation failed.

## The base course

`base/Source` is a real Adapt course holding **one sample of every component the
automation can emit**, built from `base/Inputs`'s storyboard so the two stay in
step. `base/README.md` covers what lives there, the values set by hand in it,
and how to rebuild it. Keep another course's media out of it.

## Which storyboard is the reference

`Inputs/BBIO_1468_Attruby_Product_Mod_D7v9_programming_QC/` is the most recent
project and is **the reference storyboard**. Where two courses use a convention
differently, BBIO's reading wins and the other is accommodated alongside it —
never at its expense.

In practice that means the style sets in `config.py` are supersets rather than
replacements, and a change is only correct if BBIO's output is unchanged by it.
To check that, keep a copy of `Output/<BBIO>/src/course/` before the change and
diff a fresh build against it; every file should be byte-identical unless the
change was specifically intended for BBIO.

The one deliberate exception on record: the `Disclaimer` callout on the
Introduction page is authored entirely in `Normal`, so it used to produce an
empty callout and spill its copy into the page. It now becomes a proper callout
titled "Disclaimer" — see *loose interactivity copy* below.

## How the storyboard is read

Parsing is driven by Word **styles**, not by guessing at text, which is what
makes it reliable. The mapping lives in `adapt_builder/config.py`.

| Storyboard style | Becomes |
| --- | --- |
| `Heading 1` | page (contentObject) |
| `Heading 2` | article |
| `Heading 3` / `4` / `5` | block |
| `Normal`, `List Paragraph`, `Bullet list level 1/2` | body copy → `text` component |
| `Number bullet list 1` | an ordered list (`<ol>`), or reference entries on the References page |
| `Interactivity-Heading-1` | starts an interactivity (see below) |
| `Interactivity-Heading-2` | one accordion panel / tab / hotspot |
| `Interactivity-Bullet-1`, `Interactive-bullet-2`, `Interactivity-body` | that item's copy |
| `Interactivity-Label` | figure caption / attribution |
| `footnote/diagram label`, `Diagram label 1` | caption — on the graphic above it, or on the table below it |
| `CYP-Question`, `CYP - Answer`, `CYP - TrueFalse` | assessment questions |
| `il Reference` | References page list |
| `Refrence text` | a whole paragraph of source citations — dropped (kept on the References page) |

Storyboards disagree about these conventions, so several styles are accepted for
one role. That is why the sets in `config.py` are sets.

Character styles carry meaning too:

- **`Glossary item Char`** → `<span class="notify g-term" id='…'>` plus a
  `_notifyAnywhere` entry, with the definition pulled from the Glossary table.
- **`Refrence text Char`** *(sic, the storyboard's spelling)* → a medical/legal
  source citation. Only its **bracket groups** are citations and are stripped;
  copy the style was painted over by mistake (*"AGV is calculated by…"*, a
  leading *"Its"*, the space between two sentences) is kept. A citation whose
  `]` was typed unstyled (`[Chan 2022` styled + ` p265/B]` plain) is stripped
  whole, and so are `{Animation: …}` placeholders and source URLs inside it.
- **`Programming-Notes`** → an instruction addressed to whoever builds the
  course (*"[Please remove superscript 'a' from the figure]"*). Stripped from
  the copy and listed in the report, because each one still needs doing.
- `Bold` → `<strong>`, for storyboards that came through Word Online and carry
  a character style where they would otherwise carry direct formatting.
- `annotation reference` → Word comment anchors, dropped.
- `normaltextrun`, `eop`, `cf01`, `Body Text Char` and friends → Word Online
  and pasted-text artefacts, passed through as ordinary copy.

**Boxed interactivities.** Some storyboards draw each interactivity inside a
1x1 table, or stack two in one table (a row each), with the label as the first
line. A table whose every non-empty cell opens with a label is read as boxes,
not data. Inside a box, panel headings are found by the box's own habit, tried
in order: heading-styled lines (`Heading 4`, `Interactivity-Heading-2`), then
wholly bold lines, then short plain lines. Bracketed asides in the label are
ignored (`Tabs [Programming Note: ...]`), while bracketed type words are kept
(`[Vertical] Tabs`). A hot-spot box whose drawing groups several photos gets
one composed backdrop (`...-composite.jpg`) with a pin centred over each photo.

**Other conventions read:**

- **Key Concepts: accordion or video.** A `Video: <file>.mp4` line of its own
  under the heading (styled `Programming-Note`) makes that chunk a video
  component wired to that filename; with no such line it stays an accordion.
  `Poster: <file>.png` on the same line or its own sets the poster frame.
  The file need not have been delivered yet - the component is built and the
  report says the file is still to come. Deliver videos, their `vtt/<name>.vtt`
  captions and posters in `Inputs/<course>/assets/videos/`; they are copied
  into the staged course, and anything named but missing, or delivered but
  unused, is reported. A poster is taken from the name in the storyboard, else
  `<video>-poster.png`, else the video's own first frame where ffmpeg or
  imageio-ffmpeg is available, else the theme default.
- A chapter's `Check Your Progress` / `Answers` promoted to `Heading 1` still
  belongs to the chapter above.
- `Key Concepts (For Print)` is not built. `Key Concepts (For Programming)` is
  built as `Key Concepts`. On a Key Concepts page the narration table becomes
  **an accordion** - one panel per topic, titled by the first line of its
  on-screen text, exactly as the authored course presents it - and the
  narration is published in the report for whoever records the voiceover.
  Set `config.KEY_CONCEPTS_AS_ACCORDION` to `False` to get a media component
  instead. Anywhere else a narration table is still a video.
- A question numbered by its author (`7. In PROPEL 3, ...`, and `4.	B` in the
  Answers list) keeps the number out of the shipped copy; the build numbers
  questions itself.
- A matching question's key is read per stem letter, so two stems may share one
  answer ("Secondary outcome" twice). The dropdown then offers each distinct
  answer once and stops demanding a unique answer per row.
- `Emphasis` marks italic the way `bold` marks bold: direct formatting wins.
- A figure pasted as a Windows metafile (`.emf` / `.wmf`, typical of a Visio or
  PowerPoint diagram) is rasterised to PNG - no browser can display one.
- An accordion or narrative panel holding more than one figure keeps the first
  as the panel image and the rest inline in its copy, where the author put them.
  In an accordion, a figure that comes *after* some of the panel's copy stays
  inline too, directly above its caption.
- A heading with no copy of its own, followed straight away by a deeper heading
  (`Heading 3` "PROPEL 2 Results" → `Heading 4` "Baseline Demographics"),
  titles the block; the deeper heading leads the block's copy as an `<h4>`.
- Glossary terms: runs styled separately but separated only by a space
  ("spinal" "stenosis") are one term; a style that stops mid-word ("mode|l")
  takes the whole word; one span covering several defined terms ("otitis media,
  potentially leading to conductive hearing loss") marks each of them; a term
  written abbreviation-first ("NT-proBNP (…)") matches the table's
  "… (NT-proBNP)". A term with no definition anywhere, or no letters at all
  (a styled full stop), is built as **plain text** and reported - never an
  empty popup. Citations in the Glossary table's cells are stripped.
- `List Paragraph` carrying Word numbering is a list item, not a paragraph.
- A picture pasted into a list item: a small one (≤ `LIST_ICON_MAX_PX`) is that
  item's bullet icon, marked up as the authored course does
  (`<ul class='custom-img-bullet'><li><img class='bullet-img' …><div>…</div>`);
  a larger one is placed after the list so the list stays whole.
- A programming note containing **"side by side"** is carried out: the
  picture(s) and copy next to the note become a left/right pair (the one that
  comes first takes the left). Several pictures are stacked into one
  (`…-stack.jpg`); if the note mentions a list, the paragraphs leading into the
  list stay full width above the pair. Notes carried out leave the report.
- **"How to Use This Module"** is built from the Figma template
  (`config.HOW_TO_USE_ROWS`: four text + player-icon rows), not from the
  storyboard's print copy. `config.HOW_TO_USE_TEMPLATE = False` turns this off.
- A superscripted full stop or space is a slip, not a footnote mark - built as
  plain text. On the References page, an entry typed in the `Refrence text`
  style is still a reference.
- A hotspot authored as a bare "Hotspot N" with no title is reported, since its
  popup opens untitled.
- A "put in the correct order" question whose key is a letter sequence becomes
  a `matching` question with First/Second/... dropdowns.
- The `Programming-Note` paragraph style, `{Animation: ...}` placeholders, and
  bare image-source URLs go to the report's programming notes.
- A run's direct bold/not-bold beats its character style. The answer-marker
  cross-check depends on this.
- A second callout in a row gets its own `blank` component to sit on, and a
  pending callout never crosses a page break. This matches how the authored
  course hosts them (e.g. `c-200-2`).

`Interactivity: <type>` labels map to components:
`Accordion` / `Accordions` → accordion, `Tabs` / `Horizontal Tabs` /
`Vertical Tabs` → tabs, `Hot Spots` / `Hotspot Image` → hotgraphic,
`Callout` → an `adapt-hint` box attached to the component it follows
(`ZOOM IN` and `QUICK FACT` pick the icon).

Two label conventions are in circulation and both are read:

```
Interactivity: Vertical Tabs      the type after the colon
Accordion: Learning Objectives    the type before it, its own heading after
End Interactivity: Accordions     closes the open one
```

Without that last line the label would ship as body copy.

**Loose interactivity copy.** Where the copy under a label was left styled
`Normal`, the first such paragraph can only belong to that label, so it is
claimed — and once one paragraph has been claimed the rest of the run is
claimed too, up to the next heading. Claiming only the first would leave a
callout holding its heading while its body spilled into the page. For a callout
that first line becomes the title. An interactivity whose panels were never
marked up at all is published as a single panel rather than dropped.

This engages **only** when nothing under the label was styled correctly, so a
properly authored interactivity is never affected by it.

## Tables

A storyboard table is one of five things. Which one it is decides the component
it becomes, and it is worked out from the table's own content rather than from
where it sits, because storyboards disagree about placement.

| Kind | Recognised by | Becomes |
| --- | --- | --- |
| glossary | on the `Glossary` page | the glossary table, plus the definitions behind every inline term |
| narration | a `Narration` / `On Screen Text` header row | a `media` video component, plus its script in the report |
| matching | under Check Your Progress, with a column of `A.`-lettered stems | a `matching` component |
| grid | under Check Your Progress, with two or more columns holding only `X` | a `selectchoice` component |
| data | anything else | an HTML table appended to the copy that introduces it |

Anything unrecognised falls through to **data**, which is the safe default: the
content ships and can be restyled by hand rather than being silently dropped. A
`Table 1-1: …` caption is held for the table below it, while a `Figure 1-3: …`
caption attaches to the graphic above it — they share one Word style.

**Matching and grid questions are authored as tables, twice.** The Check Your
Progress copy poses the question and the Answers copy repeats it with the key
filled in; the build reads both. Where a storyboard fills the key in on the
first copy instead, that is used and the second is still consumed, so the answer
keys below it stay lined up with their own questions.

**Key Concepts videos cannot be produced by this build.** The storyboard
specifies them as narration plus on-screen text, so the build emits the `media`
component wired to the filename the video must be delivered under, and prints
the full script in the report for whoever produces it.

## Values inherited from base/Source

A few things a course needs are not in the storyboard and never will be.
Hotgraphic pin coordinates are the standing example: a storyboard has no way to
say *"put this pin 22% from the left"*.

They **are** in `base/Source`, which is the authored course someone has already
positioned by hand — so that is where they are read from. `base/Source` is the
single place a hand-set value lives, and there is no second copy to keep in
step with it.

| Value | Read from |
| --- | --- |
| hotgraphic `_top` / `_left` per hotspot | the matching hotgraphic in `base/Source` |

The catch is that **IDs do not survive**: this build regenerates them from the
storyboard's structure, so the authored `c-125` is this build's
`c-03-03-01-02`. Matching is therefore by kind and position for components, and
by **title** for the items inside them — never by `_id`. Reordering a hotspot in
the storyboard moves its pin with it; renaming one falls back to its position.

To reposition a pin, move it in `base/Source` and rebuild. If `base/Source` has
no counterpart for a hotgraphic, that one keeps its evenly spaced placeholder
pins and the report says which component needs attention.

This replaced an `overrides/` folder that restated the same coordinates in a
second file. It was pure duplication — every title, body and strapline in it was
already identical to what the build generated, and the only fields that actually
mattered were the two pin coordinates already sitting in `base/Source`.

## Course identity

Nothing that names the course is hard-coded, so building a different storyboard
never ships under the previous module's name. Each of these is derived per
build:

| Field | Comes from |
| --- | --- |
| `course.title`, `course.body`, `_globals._moduleTitle` | the storyboard's title (below) |
| Congratulations page copy | the same title, via `config.SYNTHETIC_PAGES` |
| `_resources` "Print" download | the PDF in `Inputs/<course>/`, copied to `assets/pdf/` |

The title is looked up in order: **Word document properties** → **page header**
→ **filename** (with `_programming QC`, `-Print_v2`, `final` and `draft`
suffixes trimmed). The report says which was used. Set
`config.COURSE_TITLE_OVERRIDE` to force one.

Trademark symbols are handled for you: `Attruby® Product Module` becomes
`Attruby&reg; Product Module` in `title` and `Attruby<sup>&reg;</sup> Product
Module` wherever it is displayed.

The print PDF is renamed with the same underscore rule, and any PDF inherited
from `base/Source` is deleted from the staged theme. Because the PDF is read
from the course's own Inputs folder, it can never be another course's.

## Things worth knowing

**Answer keys are cross-checked.** The storyboard states the answers twice —
once in the `Answers` section, once by emboldening the correct option. The
build compares them and warns on any disagreement. The bolding is an authoring
marker, so it is stripped from the shipped option text.

**Runs are merged before rendering.** Word splits styled text arbitrarily
(`'v'` + `'itamin A'`), so adjacent runs sharing a formatting signature are
joined first — otherwise glossary terms fragment.

**Over-broad glossary spans are narrowed.** Where the storyboard paints the
glossary style across a whole clause, the build finds the longest term from the
Glossary table inside it and marks only that.

**Figures bind by relationship id**, not by counting, so a drawing that the raw
XML and python-docx disagree about cannot shift every later image.

## Layout

```
adapt_builder/
  config.py           style names, labels, defaults — tune conventions here
  paths.py            course discovery; theme and language resolution
  model.py            the storyboard tree (knows nothing about Word or Adapt)
  docx_reader/
    parser.py         style state machine: .docx -> model
    inline.py         runs -> HTML; glossary spans, citation stripping
    images.py         figure extraction and naming
  builders/
    ids.py            deterministic _id and _trackingId allocation
    {config,course,content_objects,articles,blocks}_json.py
  templates/          one module per Adapt component type
    question.py       shared scaffolding for the question components
  inherit.py          hand-set positions read back out of base/Source
  validate.py         structural checks run on every build
  course_copy.py      staging the full source tree
  report.py
```

## Components

Every component below has a template in `adapt_builder/templates/` — one file
each — and its plugin installed in `base/Source`. Every build checks that
pairing and warns when a component's plugin is missing, because Adapt renders
a hole rather than an error in that case.

| Component | Asked for by |
| --- | --- |
| `text` | body copy, and data tables |
| `graphic` | an image in the storyboard |
| `media` | a `Narration` / `On Screen Text` table |
| `accordion` | `Interactivity: Accordion` |
| `tabs` | `Interactivity: Tabs` / `Horizontal Tabs` / `Vertical Tabs` |
| `narrative` | `Interactivity: Narrative` / `Carousel` |
| `hotgraphic` | `Interactivity: Hot Spots` / `Hotspot Image` |
| `graphicSlider` | `Interactivity: Graphic Slider` / `Image Slider` |
| `textwithpopup` | `Interactivity: Text with Popups` / `Popups` |
| `table` | `Interactivity: Table`, followed by the table |
| `blank` | `Interactivity: Spacer` / `Blank` |
| `mcq` | a Check Your Progress question |
| `gmcq` | `Interactivity: Graphic MCQ` / `Image MCQ` |
| `matching` | a CYP table with `A.`-lettered stems |
| `selectchoice` | a CYP table of `X` columns |
| `slider` | `Interactivity: Slider`, with `Scale: 1 to 10` / `Answer: 7` panels |
| `textinput` | `Interactivity: Text Input`, one panel per accepted answer |
| `assessmentResults`, `pageNav` | added automatically |

`Documentation/Template_Reference/` holds a storyboard that exercises all of them, and
a guide to the conventions — build it after changing the parser.

To support a new component: add a module to `templates/`, register it in
`templates/__init__.py` along with its plugin name, and add the storyboard
label to `config.INTERACTIVITY_MAP`. Nothing in the parser or builders changes
unless the component needs data the parser does not already collect.

## IDs

IDs encode position, so the same storyboard always produces the same IDs and
diffs between builds stay readable:

```
co-02-ch1                 page
  a-02-03                 article 3 of page 2
    b-02-03-01            block 1 of that article
      c-02-03-01-01       component 1 of that block
```

`_trackingId` is assigned sequentially in document order, and
`course._latestTrackingId` is set to the highest value used.

Because IDs are regenerated from scratch, they differ from the previous hand
authored course — existing SCORM bookmarks and suspend data will not carry over.

## Known gaps

- **Hotgraphic pin coordinates** are not in the storyboard. They are read
  from `base/Source` instead — see *Values inherited from base/Source*. A
  hotgraphic with no counterpart there still gets evenly spaced placeholder
  pins, and the report says so.
- **Key Concepts videos** are referenced but not produced; see the report.
- **The Congratulations page** is not in the storyboard; it is generated from
  `config.SYNTHETIC_PAGES`.
- `config.json` is a passthrough of `base/Source`, and `course.json` keeps its
  player settings (audio, drawer, resources, accessibility) — only the title,
  glossary and tracking id are rewritten from the storyboard.
