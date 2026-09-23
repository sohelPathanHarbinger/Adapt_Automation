"""Recolour the theme GUI images from the Attruby palette to BBIO 1560.

The old art uses three colour families - purple for the normal state, pink for
hover, cyan for the fast-forward/flash-back icon - so each family is moved onto
its BBIO 1560 counterpart by hue. The new design is flat, so a family becomes
one solid colour: the gradients are removed, while anti-aliased edges keep
their blend and stay smooth. The background artwork is the one thing in the
design that is still a gradient, and it comes from the Figma file untouched.
"""
from __future__ import annotations

import colorsys

import sys
from pathlib import Path

from PIL import Image

ORANGE = "#f59b42"   # Figma "Orange": normal state
BLUE = "#0072ce"     # Figma "Blue": hover / active, page header, progress
SAND = "#f6ebdb"     # Figma "sand": panel tints
INK = "#000000"      # Figma "Amgen 8": line drawings and body text

#: (low, high) hue in degrees -> target colour. A band may also be split by
#: lightness, because one purple does two jobs in the same picture.
ICONS = [
    ((240, 310), ORANGE),   # Attruby purple  -> Orange
    ((310, 360), BLUE),     # Attruby pink    -> Blue
    ((175, 240), BLUE),     # the cyan icon   -> Blue
]

#: The How-to-Use illustrations are little mock-ups of a page: the dark bar is
#: the page header (blue in this design), the circles are callout icons
#: (orange), and the pale pink panels are the sand tint.
MOCKUP = [
    ((240, 310), ORANGE),   # icons and accents
    ((310, 360), SAND),     # pale pink panels
    ((175, 240), BLUE),
]

#: In a mock-up the page header is a bar running most of the way across, while
#: an icon never does - so a wide horizontal run of colour is the header, which
#: is blue in this design, and everything else is an icon, which is orange.
WIDE_RUN = 0.35

#: The progress bar is blue in every state.
PROGRESS = [((240, 310), BLUE), ((310, 360), SAND), ((175, 240), BLUE)]

#: A brushed circle behind a line drawing: the circle takes the accent colour
#: and the drawing on top of it stays dark, so the two are split by lightness.
BLOB = [
    ((240, 310, 0.0, 0.45), INK),     # the line drawing
    ((240, 310, 0.45, 1.0), ORANGE),  # the brushed circle
    ((310, 360), ORANGE),
    ((175, 240), BLUE),
]

PER_FILE = {
    "callout.png": MOCKUP, "cyp.png": MOCKUP, "expand.png": MOCKUP,
    "flashback.png": MOCKUP, "glossary.png": MOCKUP, "zoom.png": MOCKUP,
    "progress.png": PROGRESS,
    "learning_objectives.png": BLOB, "module_summary.png": BLOB,
    "welcome.png": BLOB,
}

MIN_SAT = 0.12   # below this a pixel is grey/white: left alone
MAX_LIGHT = 0.97


def _hls(hex_colour: str) -> tuple[float, float, float]:
    r, g, b = (int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return colorsys.rgb_to_hls(r, g, b)


def _coverage(rgb: tuple[int, int, int]) -> float:
    """How far this pixel sits from white, on its own colour's terms.

    Mixing a colour with white lifts every channel towards 255, so the
    darkest channel says how much colour is present - whatever the hue. That
    keeps the measure honest when the source and target hues differ.
    """
    return 1.0 - min(rgb) / 255


def _flatten(rgb: tuple[int, int, int], target: str, reference: float) -> tuple[int, int, int]:
    """Rebuild a pixel as ``white -> target`` at the coverage it already had.

    ``reference`` is the coverage of the solid areas of this band, so a pixel
    at or beyond it - including the whole of an old gradient - lands exactly
    on the flat target colour, while a pale anti-aliased edge keeps its mix
    and stays smooth.
    """
    tr, tg, tb = (int(target[i:i + 2], 16) for i in (1, 3, 5))
    t = min(1.0, _coverage(rgb) / reference) if reference else 1.0
    return tuple(round(255 + (c - 255) * t) for c in (tr, tg, tb))


def _band(bands, hue_deg: float, light: float) -> str | None:
    for spec, target in bands:
        low, high = spec[0], spec[1]
        if not low <= hue_deg < high:
            continue
        if len(spec) == 4 and not spec[2] <= light < spec[3]:
            continue
        return target
    return None


def _wide_runs(image: Image.Image) -> set[int]:
    """Indices of pixels sitting in a wide horizontal run of solid colour."""
    width, height = image.size
    pixels = image.load()
    wide: set[int] = set()
    for y in range(height):
        start = None
        for x in range(width + 1):
            solid = False
            if x < width:
                r, g, b, a = pixels[x, y]
                if a > 8:
                    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
                    solid = s >= MIN_SAT and l <= MAX_LIGHT
            if solid and start is None:
                start = x
            elif not solid and start is not None:
                if x - start >= width * WIDE_RUN:
                    wide.update(y * width + i for i in range(start, x))
                start = None
    return wide


def recolour(path: Path, dest: Path, bands=None, split_wide: bool = False) -> bool:
    bands = bands or ICONS
    image = Image.open(path).convert("RGBA")
    wide = _wide_runs(image) if split_wide else set()
    pixels = list(image.getdata())

    # The design is flat: every button, icon and panel is one solid colour, so
    # the gradient the old art used is not carried over. Each coloured pixel is
    # read as its source colour mixed with white - which is all an
    # anti-aliased edge or a soft glyph blend is - and that same mix is
    # rebuilt from the flat target colour, so edges stay smooth while the
    # gradient flattens out.
    targets: list[str | None] = []
    coverage: dict[str, list[float]] = {}
    for index, pixel in enumerate(pixels):
        r, g, b, a = pixel
        target = None
        if a >= 8:
            h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
            if s >= MIN_SAT and l <= MAX_LIGHT:
                target = _band(bands, h * 360, l)
                if target == ORANGE and index in wide:
                    target = BLUE  # the page header bar, not an icon
        targets.append(target)
        if target:
            coverage.setdefault(target, []).append(_coverage(pixel[:3]))

    if not coverage:
        return False

    # What "solid" means for each band in this picture: the bulk of its
    # pixels, ignoring the palest edges.
    reference = {
        target: sorted(values)[int(len(values) * 0.6)]
        for target, values in coverage.items()
    }

    out = []
    for pixel, target in zip(pixels, targets):
        if not target:
            out.append(pixel)
            continue
        out.append((*_flatten(pixel[:3], target, reference[target]), pixel[3]))

    result = Image.new("RGBA", image.size)
    result.putdata(out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    result.save(dest, "PNG", optimize=True)
    return True


def main(source: Path, dest: Path, skip: set[str]) -> None:
    changed = kept = 0
    for path in sorted(source.rglob("*.png")):
        rel = path.relative_to(source)
        if rel.as_posix() in skip:
            # Copied as it is: the logo and the background artwork come from
            # the Figma file, not from recolouring the old ones.
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            (dest / rel).write_bytes(path.read_bytes())
            kept += 1
            continue
        if recolour(path, dest / rel, PER_FILE.get(path.name),
                    split_wide=PER_FILE.get(path.name) is MOCKUP):
            changed += 1
        else:
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            (dest / rel).write_bytes(path.read_bytes())
            kept += 1
    print(f"recoloured {changed}, copied unchanged {kept}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]),
         set(sys.argv[3].split(",")) if len(sys.argv) > 3 else set())
