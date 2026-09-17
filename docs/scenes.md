# Scenes: the spec, the depth bands, and the solver

A scene is a JSON spec plus a set of grid modules. Compositing happens at the
**character-grid level** — layers are lists of strings and blitting is writing
characters into a canvas — so the finished frame is itself a grid and the same
assertions that police a single sprite run over the whole thing.

```
scenes/meadow.json  ->  scene.py  ->  assets/meadow*.gif + *.png
                           |
                    check_scene.py
```

## Depth bands

`base` is the scene row an object's **lowest opaque row** lands on. A smaller base
row is further from the camera, drawn first, and occluded by what follows.

**Keep the layer list sorted by base row.** The compositor draws in array order,
so a mis-sorted list inverts the occlusion silently.

The current meadow uses eight bands:

```
base 74   haystack                     furthest
base 76   fence, scarecrow
base 78   house
base 79   farmer, dog, chicken         the actors stand on the ground line
base 83   well
base 84   wagon
base 86   tree, bush
base 88   signpost, logpile, stump
base 90   flowers, mushrooms, barrel, milkchurn
base 91   rock, crate                  nearest
```

Two conventions worth keeping:

- **Actors sit on `ground_line`** and are drawn before the nearer props, so a
  foreground barrel can pass in front of them. That reads as depth.
- **A ground shadow cannot live on the base row.** A base-row fill pixel faces the
  canvas edge, and the outline rule would try to outline it into a leak. Shadows
  go one row up, with the base row as the contact outline.

## Placement is solved, not nudged

Hand-placing twenty objects and re-running the check after every nudge is tedium,
and tedium is where a layout quietly violates a rule nobody re-checked.
`plan_scene.py` splits the job the way it actually divides:

- **which depth band an object stands on** is an art decision — it sets occlusion
  and the reading of near and far. A human picks it.
- **the x position within a band** is constraint satisfaction. The solver does it,
  greedily, searching outward from an authored hint so the layout stays close to
  the intent.

```bash
python plan_scene.py --dry-run    # show the plan
python plan_scene.py              # rewrite the spec
```

If a band is too crowded it **refuses to place the object and says so**, and will
not write the spec at all. A spec with unresolved objects is worse than the one
already on disk. This earned its keep immediately: it stopped at 19 of 20 objects
and that refusal is what revealed the canvas was simply too narrow.

## The composition rule, and its two recalibrations

**Two objects may not overlap in x while sharing a dominant colour.** Overlap plus
shared identity is what makes two objects read as one.

This is the assertion form of a real complaint: the dog was drawn in the fence's
own wood brown and stood *on* the fence, and the rock sat inside the cottage's
stone foundation in the same stone.

It took two attempts to state it correctly, both corrected by measurement:

**Attempt 1 — comparing full colour sets is useless.** `K` alone is 24–57% of any
small prop, and any two wooden props share `{T, t}` by construction. The well and
the cottage "shared" **eight** colours purely because both are built from stone,
wood and plaster. That is correct art, not a defect. The comparison now uses
**dominant colours** (`dominant_top`, default 3, outline excluded).

**Attempt 2 — "close together" was the wrong test.** The complaint was that the
dog was standing **on** the fence, not merely near it, and a crate six pixels from
a fence is an ordinary farmyard. The hard test is now genuine **x-overlap**
(`overlap_gap`, default 2). Proximity produces an informational note, not a
failure.

## When the canvas is too narrow

160px could not hold twenty objects. Half of them are wood, and the overlap rule
pushes same-coloured objects apart, so the log pile had nowhere to stand.

The canvas is now **320 wide — exactly two 160px sky tiles and two ground tiles**,
so both seams are exact rather than cut mid-pattern. If you widen a scene, widen
it by an integer multiple of the layer tile width, or you will get a visible
discontinuity where a tile restarts part-way across.

## Spec format

```jsonc
{
  "size": [320, 96],
  "ground_line": 79,
  "loop_frames": 16,
  "frame_ms": 120,

  "composition": {
    "overlap_gap": 2,        // x-overlap within this many px counts as overlapping
    "dominant_top": 3,       // how many of an object's top colours are its identity
    "min_gap": 8,            // below this, print an informational note
    "ignore_colours": ["K"]  // the universal outline is not identity
  },

  "layers": [
    {"name": "backdrop", "module": "sky", "attr": "BACKDROP", "x": 0, "y": 0,
     "tile_horizontal": true},
    {"name": "farmer", "module": "walk_cycle", "attr": "FRAMES", "x": 100, "base": 79,
     "animated": true, "phase": 0}
  ],

  "effects": [
    {"name": "chimney_smoke", "type": "smoke", "x": 243, "top": 48, "puffs": 4}
  ]
}
```

Layer keys:

| key | meaning |
|---|---|
| `x`, `y` | fixed placement |
| `x`, `base` | pin the grid's lowest opaque row to a scene row |
| `tile_horizontal` | repeat across the canvas |
| `scroll_px_per_frame` | animate the tile offset |
| `animated` | the attribute is a list of frames; `phase` offsets the clip |

## Loops must close arithmetically

`check_scene.py` composites frame `loop_frames` — one past the last rendered
frame — and asserts it is **pixel-identical to frame 0**. Not "looks similar";
identical. Every animated element is designed to return to its exact start:

```
4-frame walk        16 / 4 = 4 cycles            exact
4-frame trot        16 / 4 = 4 cycles            exact
clouds 4px/frame    16 x 4 = 64px = 1 tile width exact
4 smoke puffs       each fades out before wrap   exact
```

So the seam is not tuned away. It cannot exist.

## Files

- `scenes/*.json` — the specs
- `scene.py` — spec → resolve layers → composite → frames + GIF
- `plan_scene.py` — the placement solver
- `check_scene.py` — scene assertions, loop closure, composition
