# base/Inputs — the reference input folder

This is what a course folder under `Inputs/` looks like. **It is never built as
a live course**: copy its layout when starting a new one.

It is also the storyboard `base/Source` was built from, so the base course and
this folder describe the same module.

```
base/Inputs/
  Base Sample Module.docx          the storyboard - the newest .docx is the one read
  Base Sample Module - Print.pdf   becomes the Resources drawer's "Print" download
  assets/images/Course/            hi-res originals of the storyboard's figures
  assets/images/Player/            player (theme GUI) art, laid out like the theme's assets/GUI
  assets/videos/                   video, its .vtt captions and the poster frame
  assets/audios/                   audio
  theme/less/zz-course-theme.less  the course's palette, laid over the theme
  reference/                       the documents that came with the course (Figma, source storyboard)
```

Everything except the `.docx` is optional. A folder with no `.docx` is not a
course and is passed over.

| Folder | What the build does with it |
| --- | --- |
| `assets/images/Course/` | Each file replaces the storyboard figure it *looks like*, so names don't matter. Delivered art is usually print resolution and is scaled down to `config.IMAGE_MAX_SIDE`. Needs Pillow. |
| `assets/images/Player/` | Overwrites the theme file at the same path under `assets/GUI`. A file with no counterpart there is reported and skipped. |
| `theme/` | Copied over the staged theme. `less/zz-course-theme.less` sorts last, so it can redefine the palette without touching `base/Source`. |
| `reference/` | Ignored by the build. Keep the Figma file and the original storyboard here. |
| `assets/videos`, `assets/audios` | **Not read by the build.** Media is delivered into the staged course's theme by hand; these files are the ones `base/Source` uses. |

## The sample media

The whole base course is built from these few files, each used several times:

| File | Used as |
| --- | --- |
| `bright_image.jpg` | the sample figure, a carousel panel, a graphic-slider stop, a picture answer |
| `dark_image.jpg` | the hot-spot image, a carousel panel, the other graphic-slider stop |
| `avatar.png` | the side-by-side picture, a carousel panel |
| `icon-avatar.png` | the bullet icon in the icon list (small pictures in a list item become its bullet) |
| `sample.mp4` + `vtt/sample.vtt` + `poster.png` | the video component |
| `sample.mp3` | audio |
| `Base Sample Module - Print.pdf` | the Resources drawer download |

## Regenerating the storyboard

The storyboard is generated, so its Word styles are exactly the ones the parser
reads:

```bash
python tools/make_base_storyboard.py     # rewrite Base Sample Module.docx
python build.py base/Inputs --no-copy    # check it builds (writes to _scratch/)
python build.py base/Inputs --no-copy --apply   # rebuild base/Source from it
```

`--apply` backs up `base/Source/src/course` into `_backups/<timestamp>/` first.
After it, set by hand the values a storyboard cannot express: hot-spot pin
positions, the video's file paths and the picture-answer images. They are
listed in `base/Source`'s own README.
