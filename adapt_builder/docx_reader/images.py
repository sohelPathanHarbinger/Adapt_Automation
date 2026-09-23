"""Extract storyboard images with meaningful, Adapt-friendly filenames.

Word stores a .docx as a zip; the raw bitmaps live in ``word/media/`` under
useless names (image1.png, image2.jpeg...). This module walks the document body
in reading order, maps each drawing back to its media part, and names it from
the nearest "Figure x-y: ..." caption, falling back to the picture's alt text
and then to a plain sequence number.

The returned records are in **document order**, which is what lets
:mod:`adapt_builder.docx_reader.parser` bind the Nth image it encounters while
walking paragraphs to the Nth record here.

We deliberately use regex over the XML rather than a DOM parse: document.xml for
a storyboard of this size is a couple of MB of deeply nested runs, and we only
need paragraph order, relationship ids and visible text.
"""

from __future__ import annotations

import hashlib
import html
import io
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

RE_PARA = re.compile(r"<w:p[ >].*?</w:p>", re.S)
RE_TEXT = re.compile(r"<w:t[^>]*>(.*?)</w:t>", re.S)
RE_BLIP = re.compile(r'<a:blip[^>]*r:embed="([^"]+)"')
RE_VML = re.compile(r'<v:imagedata[^>]*r:id="([^"]+)"')  # legacy VML pictures
RE_DOCPR = re.compile(r"<wp:docPr[^>]*?(?:/>|>)")
RE_DESCR = re.compile(r'descr="([^"]*)"')
#: One <Relationship> element. Word does not commit to an attribute order -
#: some storyboards write Target before Id - so the attributes are read
#: separately rather than in one positional pattern.
RE_REL_TAG = re.compile(r"<Relationship\b[^>]*/?>")
RE_REL_ID = re.compile(r'\bId="([^"]+)"')
RE_REL_TARGET = re.compile(r'\bTarget="([^"]+)"')

RE_FIGURE = re.compile(
    r"^\s*(?:Figure|Fig\.?|Table|Image|Graphic)\s*(\d[\w.\-]*?)\s*[:.\-–]\s+(.+)", re.I
)
RE_SECTION = re.compile(r"^\s*(Section\s+[\d.]+)\s*[:\-–]\s*(.+)", re.I)
RE_BRACKETED = re.compile(r"\[[^\]]*\]")  # strips "[Attruby PI p4/A]" citations

#: Windows metafiles. Word stores a pasted Visio/PowerPoint diagram as one,
#: and no browser can display it, so it is rasterised at extraction.
VECTOR_SUFFIXES = {".emf", ".wmf"}

MAX_SLUG = 60
CAPTION_LOOKAHEAD = 11  # paragraphs to scan below an image for its caption


@dataclass
class ImageRecord:
    """One drawing in the storyboard, in document order."""

    order: int
    media: str
    filename: str
    section: str = ""
    figref: str = ""
    #: "figure" or "table" - which word the caption used.
    kind: str = ""
    caption: str = ""
    alt: str = ""
    duplicate_of: str = ""
    #: Filename of the delivered original that replaced the embedded bitmap.
    original: str = ""
    data: bytes = field(repr=False, default=b"")

    @property
    def src(self) -> str:
        from ..config import FIGURE_SRC_PREFIX

        return f"{FIGURE_SRC_PREFIX}/{self.filename}"

    @property
    def title(self) -> str:
        """Human-facing label, e.g. ``Figure 3-4: Time to First Event``."""
        if self.figref and self.caption:
            return f"Figure {self.figref}: {self.caption}"
        return self.caption or self.alt


def slugify(text: str, max_len: int = MAX_SLUG) -> str:
    text = RE_BRACKETED.sub(" ", text)
    text = html.unescape(text)
    text = text.replace("&", " and ")
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    if len(text) > max_len:
        text = text[:max_len].rsplit("-", 1)[0]  # cut on a word boundary
    return text.strip("-")


def _rasterise(blob: bytes) -> bytes | None:
    """A Windows metafile as PNG, or None when it cannot be rendered here."""
    try:
        from PIL import Image

        with Image.open(io.BytesIO(blob)) as image:
            image.load()
            buffer = io.BytesIO()
            image.convert("RGBA").save(buffer, "PNG", optimize=True)
            return buffer.getvalue()
    except Exception:  # noqa: BLE001 - no renderer, or a metafile PIL refuses
        return None


def _para_text(para_xml: str) -> str:
    return html.unescape("".join(RE_TEXT.findall(para_xml))).strip()


def _open_docx(path: Path) -> tuple[zipfile.ZipFile, Path | None]:
    """Open the .docx, working around Word holding an exclusive lock on it."""
    try:
        return zipfile.ZipFile(path), None
    except (PermissionError, OSError):
        tmp = Path(tempfile.mkdtemp()) / path.name
        shutil.copy2(path, tmp)  # copy2 succeeds on a Word-locked file
        return zipfile.ZipFile(tmp), tmp.parent


def _load_rels(z: zipfile.ZipFile, part: str) -> dict[str, str]:
    """rId -> target, for one document part."""
    name = f"{Path(part).parent.as_posix()}/_rels/{Path(part).name}.rels"
    if name not in z.namelist():
        return {}
    rels: dict[str, str] = {}
    for tag in RE_REL_TAG.findall(z.read(name).decode("utf8")):
        rid = RE_REL_ID.search(tag)
        target = RE_REL_TARGET.search(tag)
        if rid and target:
            rels[rid.group(1)] = target.group(1)
    return rels


def _resolve_media(target: str) -> str:
    """Relationship targets are relative to word/, e.g. 'media/image1.png'."""
    return f"word/{target.lstrip('/')}" if not target.startswith("word/") else target


def _collect(z: zipfile.ZipFile, part: str) -> list[dict]:
    """Walk one document part in reading order, yielding one record per image."""
    if part not in z.namelist():
        return []

    rels = _load_rels(z, part)
    xml = z.read(part).decode("utf8")
    paras = RE_PARA.findall(xml)

    # Pre-compute the text of every paragraph once; we look both back (for the
    # section heading) and forward (for the caption).
    texts = [_para_text(p) for p in paras]

    found: list[dict] = []
    section = ""
    for i, para in enumerate(paras):
        if texts[i] and RE_SECTION.match(texts[i]):
            section = texts[i]

        rids = RE_BLIP.findall(para) + RE_VML.findall(para)
        if not rids:
            continue

        # Alt text, when the author set one, lives on <wp:docPr descr="...">.
        alts = [
            html.unescape(d.group(1)).split("\n")[0].strip()
            for d in (RE_DESCR.search(tag) for tag in RE_DOCPR.findall(para))
            if d
        ]

        # Caption: the nearest "Figure 3-1: ..." line at or below the image.
        # Storyboards usually put it directly beneath, but a run of footnote
        # lines (dagger, double-dagger, section marks) often sits in between -
        # hence the generous window. Stopping at the next image is what keeps
        # this from stealing a neighbouring figure's caption.
        caption = figref = kind = ""
        for j in range(i, min(i + CAPTION_LOOKAHEAD, len(paras))):
            if j > i and (RE_BLIP.search(paras[j]) or RE_VML.search(paras[j])):
                break
            m = RE_FIGURE.match(texts[j])
            if m:
                figref, caption = m.group(1), m.group(2).strip()
                kind = "table" if texts[j].strip().lower().startswith("table") else "figure"
                break

        for k, rid in enumerate(rids):
            target = rels.get(rid)
            if not target or "media/" not in target:
                continue
            found.append(
                {
                    "media": _resolve_media(target),
                    "section": section,
                    "figref": figref,
                    "kind": kind,
                    "caption": RE_BRACKETED.sub("", caption).strip(),
                    "alt": alts[k] if k < len(alts) else (alts[0] if alts else ""),
                }
            )
    return found


def _build_name(rec: dict, seq: int, prefix: bool) -> str:
    ext = ".png" if rec.get("raster") else Path(rec["media"]).suffix.lower()
    if ext == ".jpeg":
        ext = ".jpg"

    if rec["figref"] and rec["caption"]:
        stem = f"fig-{slugify(rec['figref'], 12)}-{slugify(rec['caption'])}"
    elif rec["caption"]:
        stem = slugify(rec["caption"])
    elif rec["alt"]:
        stem = slugify(rec["alt"])
    elif rec["section"]:
        stem = f"{slugify(rec['section'], 30)}-image"
    else:
        stem = "image"

    stem = stem or "image"
    return f"{seq:03d}-{stem}{ext}" if prefix else f"{stem}{ext}"


def extract_images(
    docx_path: Path,
    *,
    include_headers: bool = False,
    prefix: bool = True,
    dedupe: bool = True,
    originals: Path | None = None,
) -> tuple[list[ImageRecord], list[str]]:
    """Return ``(records_in_document_order, unreferenced_media_parts)``.

    Image bytes are carried on each record; nothing is written to disk here so
    the caller decides where the assets land. With ``originals``, a delivered
    high-resolution file replaces each embedded bitmap it matches - see
    :func:`apply_originals`.
    """
    records, orphans = _extract(docx_path, include_headers, prefix, dedupe)
    if originals is not None and originals.is_dir():
        apply_originals(records, originals)
    return records, orphans


def _extract(
    docx_path: Path, include_headers: bool, prefix: bool, dedupe: bool
) -> tuple[list[ImageRecord], list[str]]:
    z, tmpdir = _open_docx(docx_path)
    try:
        parts = ["word/document.xml"]
        if include_headers:
            parts += sorted(
                n
                for n in z.namelist()
                if re.fullmatch(r"word/(header|footer)\d*\.xml", n)
            )

        raw: list[dict] = []
        for part in parts:
            raw.extend(_collect(z, part))

        records: list[ImageRecord] = []
        by_hash: dict[str, str] = {}
        blob_by_name: dict[str, bytes] = {}
        used: set[str] = set()

        for seq, rec in enumerate(raw, start=1):
            try:
                blob = z.read(rec["media"])
            except KeyError:
                continue

            if Path(rec["media"]).suffix.lower() in VECTOR_SUFFIXES:
                converted = _rasterise(blob)
                if converted is not None:
                    # Only the shipped extension changes; "media" stays the
                    # part name the parser resolves its drawings through.
                    blob, rec = converted, {**rec, "raster": True}

            digest = hashlib.sha1(blob).hexdigest()
            if dedupe and digest in by_hash:
                # Same bitmap used twice (common for repeated icons) - point the
                # record at the first copy instead of writing a duplicate.
                name = by_hash[digest]
                records.append(
                    ImageRecord(
                        order=seq,
                        media=rec["media"],
                        filename=name,
                        section=rec["section"],
                        figref=rec["figref"],
                        kind=rec["kind"],
                        caption=rec["caption"],
                        alt=rec["alt"],
                        duplicate_of=name,
                        data=blob_by_name.get(name, b""),
                    )
                )
                continue

            name = _build_name(rec, seq, prefix)
            if name in used:  # distinct images that slugged to the same name
                suffix = Path(name).suffix
                stem = name[: -len(suffix)]
                n = 2
                while f"{stem}-{n}{suffix}" in used:
                    n += 1
                name = f"{stem}-{n}{suffix}"
            used.add(name)

            by_hash[digest] = name
            blob_by_name[name] = blob
            records.append(
                ImageRecord(
                    order=seq,
                    media=rec["media"],
                    filename=name,
                    section=rec["section"],
                    figref=rec["figref"],
                    kind=rec["kind"],
                    caption=rec["caption"],
                    alt=rec["alt"],
                    data=blob,
                )
            )

        # Anything in word/media that no drawing pointed at - usually stale
        # revisions Word kept around. Reported, not extracted.
        referenced = {r["media"] for r in raw}
        orphans = sorted(
            n
            for n in z.namelist()
            if n.startswith("word/media/") and n not in referenced
        )
        return records, orphans
    finally:
        z.close()
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Delivered originals
# ---------------------------------------------------------------------------
# A storyboard embeds figures at whatever size Word kept, often a screenshot.
# The art team later delivers the originals under their own names ("Figure
# 1-2A.jpg", "iStock-1474826033.jpg"), so they cannot be paired by name - but
# they are the same pictures, which a coarse visual fingerprint shows reliably.

ORIGINAL_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
_FINGERPRINT = 32  # px per side of the greyscale thumbnail compared


def _fingerprint(image) -> tuple[list[float], float]:
    """Mean-centred greyscale thumbnail, and the aspect ratio it came from."""
    aspect = image.width / max(image.height, 1)
    grey = image.convert("L").resize((_FINGERPRINT, _FINGERPRINT))
    pixels = list(grey.getdata())
    mean = sum(pixels) / len(pixels)
    return [p - mean for p in pixels], aspect


def _similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm = (sum(x * x for x in a) * sum(y * y for y in b)) ** 0.5
    return dot / norm if norm else 0.0


def _open(source):
    from PIL import Image  # optional dependency, only needed for originals

    image = Image.open(source)
    if image.format == "JPEG":
        image.draft("RGB", (512, 512))  # decode a print-size JPEG cheaply
    return image


def _ship(path: Path) -> tuple[bytes, str]:
    """The original's bytes, scaled down if it is bigger than a page needs."""
    from PIL import Image

    from ..config import IMAGE_MAX_SIDE

    ext = path.suffix.lower()
    ext = ".jpg" if ext == ".jpeg" else ext
    with Image.open(path) as image:
        if max(image.size) <= IMAGE_MAX_SIDE:
            return path.read_bytes(), ext
        image.thumbnail((IMAGE_MAX_SIDE, IMAGE_MAX_SIDE), Image.LANCZOS)
        buffer = io.BytesIO()
        if ext == ".jpg":
            image.convert("RGB").save(buffer, "JPEG", quality=88, optimize=True)
        else:
            image.save(buffer, "PNG", optimize=True)
        return buffer.getvalue(), ext


def list_originals(folder: Path) -> list[Path]:
    return sorted(
        p
        for p in folder.rglob("*")
        if p.is_file()
        and p.suffix.lower() in ORIGINAL_SUFFIXES
        and not p.name.startswith((".", "~$"))
    )


def apply_originals(records: list[ImageRecord], folder: Path) -> list[str]:
    """Swap each embedded figure for the delivered original it matches.

    The figure keeps its storyboard-derived name, so the course JSON is the
    same whether or not originals have arrived; only the extension follows the
    delivered file. Returns the names of originals that matched nothing.
    """
    try:
        import PIL  # noqa: F401
    except ImportError:
        return [p.name for p in list_originals(folder)]

    from ..config import IMAGE_ASPECT_TOLERANCE, IMAGE_MATCH_THRESHOLD

    candidates = []
    for path in list_originals(folder):
        try:
            with _open(path) as image:
                candidates.append((path, *_fingerprint(image)))
        except OSError:
            continue

    used: set[str] = set()
    renamed: dict[str, tuple[str, bytes, str]] = {}  # old name -> (new, data, original)

    def named_for(rec: ImageRecord) -> Path | None:
        """A delivered file whose name states the figure it is, e.g.
        "... Figure 2-1 ...png" for the storyboard's "Figure 2-1. ...".

        This is how redrawn art - same figure, new branding, so no visual
        match - is still paired with the figure it replaces.
        """
        if not rec.figref:
            return None
        word = rec.kind or "figure"
        wanted = re.compile(rf"\b{word}\s*0*{re.escape(rec.figref)}\b", re.I)
        for path, _v, _a in candidates:
            if path.name in used:
                continue
            if wanted.search(path.stem):
                return path
        return None

    for rec in records:
        if rec.duplicate_of or not rec.data or rec.filename in renamed:
            continue
        try:
            with _open(io.BytesIO(rec.data)) as image:
                vector, aspect = _fingerprint(image)
        except OSError:
            continue
        best = None
        for path, other, other_aspect in candidates:
            if abs(other_aspect - aspect) / aspect > IMAGE_ASPECT_TOLERANCE:
                continue
            score = _similarity(vector, other)
            if score >= IMAGE_MATCH_THRESHOLD and (best is None or score > best[0]):
                best = (score, path)
        chosen = best[1] if best else named_for(rec)
        if chosen is None:
            continue
        data, ext = _ship(chosen)
        new_name = f"{Path(rec.filename).stem}{ext}"
        renamed[rec.filename] = (new_name, data, chosen.name)
        used.add(chosen.name)

    for rec in records:
        if rec.filename in renamed:
            new_name, data, original = renamed[rec.filename]
            if rec.duplicate_of:
                rec.duplicate_of = new_name
            rec.filename, rec.data, rec.original = new_name, data, original

    return [p.name for p, _v, _a in candidates if p.name not in used]


PANEL_HEIGHT = 700  # px; each photo of a composed backdrop is scaled to this
PANEL_GAP = 24
PIN_TOP = 12.0  # % from the top of the backdrop


def compose_panels(blobs: list[bytes]) -> tuple[bytes, list[tuple[float, float]]]:
    """Join photos side by side on white; return the JPEG and a pin per panel.

    Pins are ``(top, left)`` in percent of the backdrop, horizontally centred
    over each panel - the units hotgraphic ``_top`` / ``_left`` use.
    """
    from PIL import Image

    panels = []
    for blob in blobs:
        with Image.open(io.BytesIO(blob)) as image:
            image = image.convert("RGB")
            width = round(image.width * PANEL_HEIGHT / image.height)
            panels.append(image.resize((width, PANEL_HEIGHT), Image.LANCZOS))

    total = sum(p.width for p in panels) + PANEL_GAP * (len(panels) - 1)
    canvas = Image.new("RGB", (total, PANEL_HEIGHT), "white")
    pins: list[tuple[float, float]] = []
    x = 0
    for panel in panels:
        canvas.paste(panel, (x, 0))
        pins.append((PIN_TOP, round((x + panel.width / 2) * 100 / total, 1)))
        x += panel.width + PANEL_GAP

    buffer = io.BytesIO()
    canvas.save(buffer, "JPEG", quality=88, optimize=True)
    return buffer.getvalue(), pins


def compose_stack(blobs: list[bytes]) -> bytes:
    """Stack pictures top to bottom on white, all at the narrowest width.

    Used where the storyboard asks for several pictures beside one piece of
    copy: a block has two columns, so the pictures share one.
    """
    from PIL import Image

    panels = []
    for blob in blobs:
        with Image.open(io.BytesIO(blob)) as image:
            panels.append(image.convert("RGB"))
    width = min(p.width for p in panels)
    panels = [
        p if p.width == width
        else p.resize((width, round(p.height * width / p.width)), Image.LANCZOS)
        for p in panels
    ]
    gap = round(width * 0.03)
    height = sum(p.height for p in panels) + gap * (len(panels) - 1)
    canvas = Image.new("RGB", (width, height), "white")
    y = 0
    for panel in panels:
        canvas.paste(panel, (0, y))
        y += panel.height + gap

    buffer = io.BytesIO()
    canvas.save(buffer, "JPEG", quality=88, optimize=True)
    return buffer.getvalue()


def first_frame(video: Path, out: Path) -> bool:
    """Grab a video's first frame as the poster, if a tool is available.

    Nothing here is a hard dependency: ffmpeg on PATH is used when present,
    then imageio-ffmpeg if it is installed. Without either, the caller falls
    back to the poster the storyboard named or the theme's default.
    """
    import shutil as _shutil
    import subprocess

    exe = _shutil.which("ffmpeg")
    if exe is None:
        try:
            import imageio_ffmpeg

            exe = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            return False
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [exe, "-y", "-loglevel", "error", "-i", str(video),
             "-frames:v", "1", str(out)],
            check=True, timeout=120,
        )
    except Exception:
        return False
    return out.is_file()


def write_images(records: list[ImageRecord], out_dir: Path) -> int:
    """Write each distinct bitmap once into ``out_dir``. Returns files written."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: set[str] = set()
    for rec in records:
        if rec.filename in written or not rec.data:
            continue
        (out_dir / rec.filename).write_bytes(rec.data)
        written.add(rec.filename)
    return len(written)
