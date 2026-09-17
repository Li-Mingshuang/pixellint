"""Authoring tool for the one procedural grid in yardprops.py: HAYSTACK.

This is NOT imported by yardprops.py and NOT imported by check_yardprops.py.  It
is the recipe that produced the haystack's literal grid once; yardprops.py holds
the frozen output, exactly the way sky.py holds frozen literals and no longer
carries its generator.  Keep this file so the dome can be re-tuned by editing a
number instead of 24 characters times 18 rows.

Run:  python gen_yardprops.py

The other three props are NOT generated.  A well rim, a scarecrow's cross and a
cart's spoked wheels are *placed* decisions -- which pixel of stone sits beside
the dark mouth, where the bucket hangs, how far the drawbar overhangs -- and
there is nothing to gain from hiding them behind a formula, so they are
hand-authored literals in yardprops.py and this tool stays out of their way.  It
only re-derives the haystack and reports whether yardprops.py still matches it.

Method, the haystack dome:

  SILHOUETTE  the outer span of each of the 18 rows is set by hand (LROW/RROW
              below): a dome that swells from 6px at the crown to 22px at the
              belly and tucks back to 20px where it meets the ground.  The edges
              jitter by 1-2px from row to row -- that is the ragged thatch, and
              it is why the left edge steps -1,-1,-2,0,-1,-1,0,-1,-1 instead of
              sweeping smoothly.

  THATCH      every pixel inside the span takes a tone from a light ramp that
              starts at the upper-left: light = 0.62 * across + 0.30 * down, so
              E (sunlit straw) only ever appears on the crown's left shoulder and
              t (deep shade) only at the lower-right and the base.  Two periodic
              strands are superimposed -- a dark one on (x + 2y) % 7 and a lit one
              on (x - y) % 5 -- which is what makes it read as straw rather than
              as a gradient.  The bottom two rows get +0.40 so the stack always
              sits in its own ground shadow, and the row above them +0.18.

  OUTLINE     after the tones are laid down, any fill pixel with a transparent
              4-neighbour (or the canvas edge) is turned into K.  That single
              pass is what gives the dome its closed dark rim -- including along
              the ragged edge, where it turns every jutting tooth into outline.

Determinism: nothing here uses `random`, dict ordering or the Python version, so
re-running this file reproduces the same 18 rows every time.
"""

from __future__ import annotations

from collections import Counter

W, H = 24, 18

# outer span per row, inclusive, hand-set: dome + ragged edge + base tuck
LROW = [9, 8, 7, 5, 5, 4, 3, 3, 2, 1, 1, 1, 1, 1, 1, 1, 2, 2]
RROW = [14, 16, 17, 17, 18, 19, 21, 20, 21, 21, 22, 22, 22, 22, 22, 22, 21, 21]

STRAND_DARK = 7        # period of the dark thatch strand along (x + 2y)
STRAND_LIT = 5         # period of the lit strand along (x - y)
BASE_SHADOW = 0.40     # added to the bottom two rows
BASE_SHADOW_1 = 0.18   # ... and to the row above them

TONES = ((0.18, "E"), (0.42, "Y"), (0.68, "N"), (0.90, "n"))   # else t


def tone(x: int, y: int, x0: int, x1: int) -> str:
    across = (x - x0) / max(1, x1 - x0)
    down = y / (H - 1)
    light = 0.62 * across + 0.30 * down
    if y >= H - 2:
        light += BASE_SHADOW
    elif y == H - 3:
        light += BASE_SHADOW_1
    if (x + 2 * y) % STRAND_DARK == 0:
        light += 0.14
    elif (x - y) % STRAND_LIT == 0:
        light -= 0.10
    for cut, key in TONES:
        if light < cut:
            return key
    return "t"


def outline(fill: list[list[str]]) -> list[list[str]]:
    """Any fill pixel facing background -- or the canvas edge -- becomes K."""
    out = [row[:] for row in fill]
    for y in range(H):
        for x in range(W):
            if fill[y][x] in (".", "K"):
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if not (0 <= nx < W and 0 <= ny < H) or fill[ny][nx] == ".":
                    out[y][x] = "K"
                    break
    return out


def build_haystack() -> list[str]:
    fill = [["." for _ in range(W)] for _ in range(H)]
    for y in range(H):
        for x in range(LROW[y], RROW[y] + 1):
            fill[y][x] = tone(x, y, LROW[y], RROW[y])
    return ["".join(row) for row in outline(fill)]


def main() -> int:
    grid = build_haystack()
    print("-- haystack recipe -----------------------------------------")
    print(f"  spans            : crown {RROW[0] - LROW[0] + 1}px -> belly "
          f"{max(r - l for l, r in zip(LROW, RROW)) + 1}px -> base "
          f"{RROW[-1] - LROW[-1] + 1}px")
    print(f"  left edge steps  : {[LROW[i + 1] - LROW[i] for i in range(H - 1)]}")
    tones = Counter(c for row in grid for c in row if c not in ".K")
    print("  tones            : " + ", ".join(f"{k} {v}" for k, v in sorted(tones.items())))

    try:
        import yardprops
    except ImportError:
        yardprops = None
    if yardprops is None:
        print("  yardprops.py not importable -- frozen rows below")
        for i, row in enumerate(grid):
            print(f'    "{row}",  # {i}')
        return 0

    if yardprops.HAYSTACK == grid:
        print("  frozen grid      : yardprops.HAYSTACK matches this recipe")
        return 0
    print("  frozen grid      : DRIFTED -- paste these rows into yardprops.py")
    for i, row in enumerate(grid):
        print(f'    "{row}",  # {i}')
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
