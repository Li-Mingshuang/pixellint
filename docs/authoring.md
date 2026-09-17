# Authoring

This document is the one that was missing: how to add a layer from scratch, and
what discipline makes parallel authoring work instead of producing churn.

## Add a layer in ten minutes

Pick a name. Say `windmill`.

**1. Write the module.** One character = one pixel = one index into the palette.
`.` is transparent.

```python
"""WINDMILL: 30x44, base row 43, for the meadow scene."""

from pixelkit import build, preview, SCENE_PALETTE

WINDMILL = [
    "..............................",
    "............KKKKKK............",
    "..........KKUUUUUUKK..........",
    # ... 44 rows of exactly 30 characters
]
```

Every module here has a module docstring naming **size, base row, and palette
keys**. Do that; it is the cheapest documentation there is and the composer needs
it.

**2b. Declare what you ship, and in which palette.** If your module assembles its
frames from named blocks, add:

```python
SHIPPED = ("FRAMES",)          # HELM/TORSO/LEGS_* are blocks, not deliverables
PALETTE = GAME_PALETTE         # only if you are not drawing in the scene palette
```

Without `SHIPPED`, `evaluate.py` measures the frames *and* every block they are
assembled from, counting the same authored cells twice. The alternative is a
hand-maintained exclusion list inside the measuring tool, and that list went stale
twice in one session. `PALETTE` exists because directory grouping is not enough:
`mechdog.py` lives at the repo root but is drawn in the game's palette.

**3. Assert the shape.** Not the picture — the shape.

```python
from pixelkit import check_grid, report_separation

problems  = check_grid(WINDMILL, "windmill", SCENE_PALETTE)          # -> []
failures, rows = report_separation(WINDMILL, "windmill", palette=SCENE_PALETTE)
```

`check_grid` catches: wrong size, a key not in the palette, floating pixels, more
than one disconnected body, a fully transparent grid.

**3. Write `check_windmill.py`.** It should assert things a person could not check
by looking:

- exact width and height
- only palette keys
- exactly one connected body, with an explicit component count
- **the lowest opaque row equals the grid's last row** — so it stands on the
  ground wherever it is placed
- every silhouette pixel facing transparency is `K`
- any geometry constant you export actually matches the pixels
- the rendered preview decodes back to the grid pixel-for-pixel

**4. Fix hard failures only.** A warning is a note, not a defect. Do not redesign
art to silence a warning — that mistake cost this project thirteen separate art
decisions. See [rules.md](rules.md).

**5. Register it in the spec** under `scenes/*.json`, in **base-row order**, then
run the solver:

```bash
python plan_scene.py --dry-run
python plan_scene.py
python build.py
```

`build.py` discovers `check_*.py` **recursively**, so your checker runs in CI
without being registered anywhere.

**6. Render a preview** into `assets/` so a human has something to look at. Every
module here exposes a `main()` that does this.

## The discipline that makes parallel agents work

This repo was largely built by dispatching several authoring agents at once. What
made that work, and what went wrong:

### Brief them with the palette, the size, and the failure policy

Every agent brief should state, explicitly:

- **the exact palette** and that it must not be modified
- **exact dimensions** for every grid, and that the lowest opaque row must be the
  grid's last row
- **the failure policy**: hard failures must be fixed, warnings are your call and
  should normally be left alone
- **the checks to run before reporting**, as literal commands

### Nothing may be verified until the writer has stopped

A full build once failed on `check_dog.py` while the dog agent was still writing
it — the check read a half-written file. Parallel authoring is fast; parallel
*verification* is not. Re-run once everything has settled.

The same rule applies to shared files. Changing `pixelkit.py` while four agents
are working is a race. One agent noticed a palette key change under it mid-flight
and had to re-run everything; it happened to survive, but that was luck.

### Ask for mutation testing

The strongest check scripts in this repo were **mutation-tested by their own
author**: deliberately break the art and confirm the check reports it.

```
head shifted one column   -> reported as dx != 0
a frame raised one row    -> lowest row drops, reported
a stray pixel             -> reported as floating
a filled base row         -> rejected as a hedge rather than a scatter
one corrupted PNG pixel   -> raster decode fails
```

An assertion that cannot fail is decoration. If you write a check, prove it bites.

### Prefer measuring over hard-coding

Two bugs came from constants that should have been measurements:

- the muzzle flash was placed at a hard-coded offset and sat **two columns right
  and two rows above** the actual barrel
- every enemy clip was indexed with a hard-coded `% 5`; the 4-frame walk repeated
  its first frame, and the 2-frame attack silently fell back to the standing pose

Both fixes were structural rather than a corrected constant: the atlas now exports
the rightmost opaque pixel per sprite, and the frame count per clip
(`window.ANCHOR`, `window.CLIPS`). **A measured value cannot drift when the art is
redrawn; a constant does.**

### Let large regular shapes be generated

Hand-authoring a 320×96 gradient is absurd. For anything procedural — a gradient,
a noise field, a tiled rhythm — write a small generator, then **freeze the output
as literal grid strings** and keep the generator beside it with a note saying so.
`gen_background.py` and `gen_yardprops.py` are the examples; both re-derive their
output and report whether it still matches.

What is *not* procedural: a face, a well rim, a cross, spoked wheels. Those are
placement decisions, not formulas.

### Report what you worked around

Every agent report here ends with the palette pairs it had to design around. That
list is how the thresholds got recalibrated. A silent workaround is a lost
measurement.

## Starting from an image instead of from nothing

If you have a reference — your own art, a 3D render, a photo, or a CC0 image — do
not hand-author the grid. Run it through `pixelate.py`:

```bash
python pixelate.py hero.png --size 56x72 --palette game --out assets/hero --animate
python pixelate.py hero.png --size 56x72 --palette game --out assets/hero \
    --module hero.py          # also emit a pipeline module
```

It does the four things that are deterministic and easy to get wrong by hand:

1. **Area-average downscale** (`BOX`, not `LANCZOS`). For pixel art you want each
   output pixel to be the *mean* of the block it covers; that is what makes the
   quantiser's job well-posed.
2. **CIELAB quantisation** to the locked palette. Nearest in RGB picks
   perceptually wrong colours constantly; nearest in Lab is the same amount of
   code and gets skin, foliage and metal right.
3. **A separation repair pass.** Naive quantisation is locally correct and
   globally wrong: it reliably produces two near-identical palette entries side by
   side on a soft gradient. The pass walks the failing pairs and moves the rarer
   colour to the nearest entry that resolves the pair without starting a new
   failure, and reports how many substitutions it made.
4. **A silhouette outline**, which is what stops a downscaled photo from looking
   like a blurred thumbnail.

Then it runs the repo's own assertions on the result.

**`--animate` is procedural and honest about it:** a one-pixel bob, nothing more.
From a single static image you cannot have a walk cycle, because a walk cycle
needs poses that are not in the picture. Anything claiming otherwise is either
morphing (which reads as melting) or a generation model.

**Licensing.** Only feed it images you have the right to derive from — your own,
or CC0 / public domain. Pixelating someone's art does not make it yours, and this
repo is public. [madjin/awesome-cc0](https://github.com/madjin/awesome-cc0) is a
good starting list.

**And the limit that matters:** `pixelate.py` has no eyesight, and neither does
anything else here. It will faithfully turn a bad source, a bad crop, or a subject
that is unrecognisable at 56×72 into a verified, palette-clean, structurally
perfect piece of bad art. **The source has to be chosen by someone who can see it.**

## Handing a layer to the game

The game loads one generated file, `game/assets.js`, containing the packed sheet
as a base64 data URI plus `ATLAS`, `ANCHOR`, `OPAQUE`, `CLIPS` and `PALETTE`.
`export_game_atlas.py` builds it from every module in `game/`. Plain globals
rather than ES module exports, because a module script is blocked by CORS over
`file://` and the demo is meant to be double-clickable.

Anything you add to `game/` gets packed automatically; then add a draw call in
`game/index.html` and a line to `game/smoke_test.mjs` proving it is drawn.
