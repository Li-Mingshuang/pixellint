# Decision log

Why things are the way they are, including what was reversed. Reversals are kept
because a decision log that only records the wins is a marketing document.

---

## 001 — Author art as character grids, not raster images

**Context.** The generator is a text-only model with no image input.

**Decision.** Represent a sprite as `list[str]`, one character per pixel, one
index into a locked palette. The grid **is** the artwork; it is not exported from
a drawing.

**Why it works.** It is diffable (a one-pixel change is a one-character diff),
reviewable (a human can read it in a pull request), and above all **assertable** —
which is what closes the loop for a model that cannot look at its output.

**Consequence.** Everything else in this repo exists to serve that third property.

---

## 002 — Assert structure and readability; never claim to assert beauty

**Decision.** The assertion suite checks correctness (closed outline, single
connected body, correct ground row, loop closure) and readability (colour
separation, relative margin). It does not and will not produce a quality score.

**Why.** There is no such metric, and inventing one would be worse than admitting
the gap. `evaluate.py` says this in its output so the numbers cannot be
misappropriated.

---

## 003 — One rule set keyed by ROLE, not two keyed by size
*Reverses an earlier decision.*

**Was.** `SPRITE_TIERS` (28/20/45) for small sprites, `SCENE_TIERS` (22/15/32) for
large shapes.

**Now.** One set keyed by whether the pair touches the outline.

**Why it was reversed.** The distinction that matters is not "how big is the
shape", it is "does this pair decide the silhouette". The old names survive as
aliases so existing call sites keep working.

---

## 004 — Hard failures and warnings are separate things

**Was.** Every threshold miss was a failure.

**Now.** A failure means a viewer could not tell two colours apart. Anything
visible but close is a warning, printed worst-first and capped at eight.

**Why.** Most tight pairs are taste, not correctness, and forcing them all to zero
is how a checker starts dictating composition.

---

## 005 — The lightness test is a RATIO as well as a step
*Reverses an earlier decision.*

**Was.** `|dL| >= 0.22`.

**Now.** `|dL| >= 0.22` **or** `max/min >= 1.7`.

**Why.** Weber's law. In a night palette 0.05 against 0.16 is a three-fold
brightness difference and reads instantly, but the absolute gap is 0.11. The old
rule declared honest night palettes unreadable. This is why the zombie shooter's
dark palette is possible at all.

---

## 006 — The `shade` / `material` taxonomy is deleted

**Was.** Three tiers with nineteen declared `SHADE_PAIRS` exceptions.

**Now.** Two roles, no exceptions.

**Why.** The nineteen exceptions existed purely to stop the checker firing on
normal shading. A taxonomy that needs nineteen carve-outs is modelling the wrong
thing.

---

## 007 — The fill floor sits at the "literally identical" line

**Was.** ΔE 45 / 32 / 20 / 15 / 12, adjusted downward five times.

**Now.** **ΔE 6** for fill pairs; ΔE 24 for outline pairs.

**Why.** Four separate failures arrived that no display could render — 0.1, 0.3,
0.03 and one that was simply wrong (see 008). The conclusion was not "lower it
again" but that a fill pair is the wrong thing to gate at all. An outline exists
to be an edge and a dissolved silhouette is unrecoverable, so that floor stays
strict.

**Cost of getting here.** Thirteen art decisions were routed around the old
floors. The tables are in [rules.md](rules.md).

---

## 008 — The `K`–`p` war story was wrong, and is corrected
*Reverses a claim made in this repo's own README.*

**Was.** "The check caught a killer: outline `K` against trouser shadow `p` at
ΔE 12.7, which would merge and destroy the silhouette."

**Now.** Under the ratio measure that actually matters, that pair is **3.2×** and
reads perfectly well. Dark trousers with a black outline is standard pixel art.

**Why it matters.** The check flagged something almost certainly fine, the palette
was changed to satisfy it, and the episode was then cited as proof the check
should stay strict. Circular reasoning. It is documented as the cautionary tale
rather than quietly deleted.

---

## 009 — Procedural generation for large regular shapes, frozen as literals

**Decision.** Gradients, noise fields and tiled rhythms are produced by a small
generator whose output is **frozen as literal grid strings**; the generator is
kept beside it and re-derives to check it still matches.

**Why.** Hand-authoring a 320×96 gradient is absurd. But the art must stay
readable-as-text for the assertion layer to work, so the frozen literal — not a
computation at import time — is the artifact.

**Not applied to.** Faces, well rims, crosses, spoked wheels. Those are placement
decisions, not formulas.

---

## 010 — Loop closure is proven, not tuned

**Decision.** `check_scene.py` composites frame `loop_frames` and asserts it is
pixel-identical to frame 0.

**Why.** Every animated element is designed to return to its exact start (4-frame
cycles over 16 frames, clouds at 4px/frame over exactly one tile width, smoke
puffs that fade before they wrap). The seam is not small; it cannot exist.

---

## 011 — Reproduction is checked at PIXEL level, not byte level
*Reverses an earlier decision, after CI caught it.*

**Was.** `git diff --exit-code -- assets`.

**Now.** `verify_reproducible.py` decodes every asset and compares pixels.

**Why.** Green on Windows, red on Linux, with the build itself passing. PNG bytes
differ across platforms and Pillow/zlib builds; the pixels do not. The project was
asserting byte equality of a compressed format, which is simply the wrong claim.

---

## 012 — Generated recordings are seeded

**Decision.** `smoke_test.mjs --dump` installs a seeded xorshift RNG.

**Why.** The game uses `Math.random` for spawn positions and particle velocities,
so an unseeded dump produced a different GIF on every build. An artifact that
changes on every build cannot be checked against its source.

---

## 013 — The layout is solved and checked, not nudged

**Decision.** `plan_scene.py` takes the depth band from the spec (an art decision)
and solves the x position (constraint satisfaction). It refuses to write a spec it
cannot fully satisfy.

**Why.** Hand-placing twenty objects and re-running the check after every nudge is
where a layout quietly violates a rule nobody re-checked. The refusal is not
theoretical: it stopped at 19 of 20 objects, which is how we learned the canvas
was too narrow.

---

## 014 — The composition rule compares dominant colours and real overlap
*Reverses an earlier formulation, twice.*

**Was.** "Objects sharing >= 2 colours within 8px, in the same depth band."

**Now.** "Objects that **overlap in x** while sharing a **dominant** colour."

**Why both changes.** Comparing full colour sets made the well and the cottage
"share" eight colours, purely because both are built from stone, wood and plaster
— correct art, not a defect. And "close together" was the wrong test: the original
complaint was that the dog was standing **on** the fence, and a crate six pixels
from a fence is an ordinary farmyard.

---

## 015 — Measure separately from gate

**Decision.** `build.py` runs the checks (which gate) and then `REPORT_STEPS`,
which are allowed to return non-zero.

**Why.** `evaluate.py` exits non-zero when an asset is unclean, but the check
scripts have already decided that. Failing the build again there would just
double-report. Measurement and gating are different jobs.

---

## 016 — Discover things by shape, never from a maintained list

**Was.** `build.py` globbed `check_*.py` non-recursively; `evaluate.py` had a
hand-written asset list.

**Now.** Both discover automatically — recursive glob, and shape-sniffing of
module attributes.

**Why.** Both lists had already gone stale. The non-recursive glob silently
skipped `game/check_*.py`; the asset list covered 28 of 44 assets. **A maintained
list omits the newest thing, and the omission looks like a clean report.**

---

## 017 — Constants that should be measurements are treated as bugs

**Examples.** The muzzle flash offset (two columns right and two rows above the
actual barrel) and the per-clip frame index (a hard-coded `% 5` that made a
2-frame attack fall back to the standing pose).

**Decision.** Both fixed structurally: the atlas exports each sprite's rightmost
opaque pixel and each clip's frame count. A measured value cannot drift when the
art is redrawn.

---

## 018 — The build is a dependency graph, not a script

**Decision.** `build.py` runs steps in parallel waves and skips a step whose outputs
are newer than the local modules it **transitively imports**, derived by parsing
with `ast`. `--force` ignores the cache.

**Why not a hand-written dependency list.** That is the artifact that goes stale in
this repo — twice already, and each time the failure was silent. A build cache with
a stale dependency is worse than no cache: it serves old output as if it were new,
and every check downstream then validates the wrong file.

**Why not chase interpreter startup.** Startup was ~2 s of an 11.1 s serial build,
spread over ~30 processes. Removing it means merging independent steps into one
process, which is precisely what destroys the parallelism that saves 4×. The
profile said rendering and checks dominated; the fix targeted those.

**Cost, stated plainly.** This trades a class of correctness for speed. CI therefore
runs `python build.py --force`, and `verify_reproducible.py` forces too — otherwise
on a fresh checkout, where every file shares a timestamp, an incremental build would
skip the very render steps the reproducibility check exists to exercise and the
check would pass trivially.

**Measured.** 12.7 s serial → 8.4 s forced parallel → 2.8 s incremental no-op.
Touching `mech.py` alone reruns one step (323 ms).

---

## Open questions

Recorded so they are not lost:

| question | why it is open |
|---|---|
| **Token cost per asset** | Not instrumented. Needs per-agent accounting from the harness; nothing in this repo can measure it. |
| **Iteration count per asset** | **Partly done.** The build now logs every check's outcome to `.pipeline-runs.jsonl` and `evaluate.py` reports consecutive failures before the most recent success, per script. It is still per **script**, not per asset, and only covers runs since logging was added. |
| **Calibrating margin against human ratings** | The margin proves the art sits near the line; it does not prove the art is good. Turning it into a quality metric requires scoring assets by hand and checking the correlation. Until then, margin is a readability proxy and nothing more. |
| **A metal key in the scene palette** | There is no uppercase `M`. The milk churn uses `W` and asserts the substitution. Adding a key nothing else uses would be dead weight. |
| **A `docs/` tutorial** | This folder. Written late. |
