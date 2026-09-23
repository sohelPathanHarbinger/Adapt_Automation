# base/ — what every course is built from

| Folder | What it is |
| --- | --- |
| `base/Source/` | the Adapt course tree every build copies: one sample of **every** component the automation can emit, and the settings each new course inherits |
| `base/Inputs/` | the reference input folder, and the storyboard `Source` was built from. Never built as a live course — see its own README |

## base/Source

It is a real, buildable Adapt course ("Base Sample Module"). Two jobs:

1. **The template.** A build copies this tree, then overwrites
   `src/course/en/*.json` with the new course. Everything else — theme,
   plugins, player settings — comes from here, so what is installed here is
   what every course gets.
2. **The example.** Its own course JSON holds one of each component, so you can
   see how a finished one looks, and `inherit.py` reads hand-set values back
   out of it.

```
base/Source/
  src/course/en/        the sample course (8 pages, 61 components)
  src/components/       19 component plugins, incl. adapt-selectchoice
  src/extensions/       14 extensions (hint callouts, glossary, notify, spoor, ...)
  src/theme/adapt-theme-ferring/
    assets/GUI/         player art - the only images the theme's CSS refers to
    assets/images/      figures extracted from the base storyboard (course art)
    assets/videos/      sample.mp4, its vtt captions, poster.png
    assets/audios/      sample.mp3
    assets/pdf/         the Resources drawer download
  node_modules/         kept so `grunt` runs here; never copied into a build
```

Every picture, video and PDF comes from `base/Inputs/assets`, reused across the
course, so the whole tree is about 38 MB rather than a course's worth of media.

## Values set by hand here

A storyboard cannot express these, so they live in `base/Source` and are read
back out of it on every build (`adapt_builder/inherit.py`):

| Value | Where |
| --- | --- |
| hot-spot pin positions (`_top` / `_left`) | the hotgraphic in `src/course/en/components.json` |
| the picture-answer images | the `gmcq` component |
| player settings: drawer, audio, accessibility, spoor | `src/course/en/course.json`, `src/course/config.json` |

A new course inherits pin positions only where a hot spot's title matches one
here; otherwise the build places evenly spaced pins and says so in the report.

## Rebuilding it

`base/Source`'s course comes from `base/Inputs`'s storyboard, so the two stay in
step:

```bash
python tools/make_base_storyboard.py              # the storyboard
python build.py base/Inputs --no-copy --apply     # rebuild this course from it
```

The video is no longer one of them: the storyboard names it
(`Video: sample.mp4, Poster: poster.png`, under Section 2.4), so the build wires
it up. Then set the hand-set values above again — `--apply` overwrites the JSON.
`_backups/<timestamp>/` holds the previous copy.

## What it must not become

- No course's own media. If a figure belongs to one client's module, it belongs
  in that course's `Inputs/` folder, not here.
- No `build/` folder: that is grunt's output and is regenerated per course.
- No nested git repository.
