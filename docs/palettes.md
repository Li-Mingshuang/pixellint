# Designing a palette

Everything here was learned by getting it wrong and measuring. A palette that
fights you costs far more than the time spent designing it properly.

## Design the value ladder first

The single most expensive mistake in this repo, made twice on two different
palettes: **picking colours that look nice, then discovering they do not
separate.**

The first scene palette had **13 failing adjacent pairs.** Dirt, wood, stone,
grass shadow and foliage had all piled into the same narrow lightness band, and
the two greens were the same hue at the same value. The game palette repeated it
exactly: 30 colours crammed between luminance 0.10 and 0.43, producing 21
failures.

Rebuilding both around an explicit ladder took them to zero:

```
K  0.045   outline
1  0.07    sky top          <- each band >= 1.7x the one above
2  0.11    sky mid
3  0.18    sky low
4  0.27    horizon haze
...
W  0.98    muzzle flash core
```

**Write the ladder before the colours.** Assign each entry a target luminance,
space them so neighbours differ enough to read, then pick hues that hit those
targets. Only after that check the palette; do not check it and then tune colours
until it squeaks through.

Current spread: the meadow palette runs 0.05 → 0.98 across 36 keys, the game
palette 0.05 → 0.98 across 39.

## Give shadows a hue shift, not just a value shift

A base colour and its shadow that differ only in lightness sit close in ΔE and
look muddy. Night art has a natural answer: **shadows go darker *and* cooler.**

```
"S": (0xe8, 0xbb, 0x92)   skin
"s": (0x9c, 0x6a, 0x56)   skin shadow -- warmer value, cooler hue
```

This is correct lighting modelling and it buys separation for free.

## Gradients are not defects

A gradient's adjacent bands are *supposed* to be close. Do not let a checker talk
you into a garish ramp. If a sky's steps are being flagged, either accept them as
warnings or widen the steps deliberately — but never dither a gradient into noise
to satisfy a number.

## Silhouettes read on lightness ratio

For a shape against a backdrop, what matters is the **ratio**, not the absolute
difference. In the night palette `5` (far skyline silhouette, luminance 0.032)
sits under every sky band by a factor of 2 to 8. That reads. An absolute-step rule
would have called it unreadable.

Put your silhouettes far below or far above the thing behind them, and check the
ratio.

## Known traps in the current palettes

Recorded rather than fixed, because retuning them invalidates verified art:

| trap | detail |
|---|---|
| `K`–`t` | outline vs wood shadow, ΔE 24.7 against the outline floor. `t` cannot touch an outline anywhere, which is why the 20px dog has flat fur. |
| `P`–`T`, `p`–`t`, `p`–`n` | ΔE 9.0 / 9.9 / 8.0 — near-identical. The scarecrow's shirt needs its own `K` garment edge wherever it meets the frame. |
| `T`–`N/n/H/h/P/p/B/b/s/u` | all under the old material floor with `dL < 0.25`. `T` (wood) is the most isolated key in the scene palette. |
| no uppercase `M` | the scene palette has no metal key. The only M-family entry is lowercase `m`, the character's mouth. The milk churn uses `W` for its highlight, and the substitution is *asserted* rather than silent. |
| `K` is 24–57% of any small prop | never compare full colour sets between props; an outline is most of a small sprite. |

## Rules of thumb

1. **Ladder first, colours second.**
2. **Shadows shift hue as well as value.**
3. **Silhouettes need ratio, not difference.**
4. **One palette per art direction.** The meadow and the game do not share one,
   and that is deliberate: a night city and a sunny farmyard cannot share a value
   ladder.
5. **Do not add a key nothing uses.** An unused palette entry is dead weight that
   still has to separate from everything.
6. When a whole class of pairs is failing, **the palette is wrong, not the art.**

## Files

- `pixelkit.SCENE_PALETTE` — the meadow/farmyard palette
- `gamepalette.GAME_PALETTE` — the zombie shooter's
- `evaluate.py` — per-asset keys used, pairs adjudicated, and relative margin
