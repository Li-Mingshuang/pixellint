"""Assertions for MECHPUP.

Held to the same standard as the 20x14 dog in `check_dog.py`, because a second
animated asset is exactly where a project starts letting standards slide:

  * every frame the size it claims, palette-closed, one connected body
  * **the ground row is identical in all four frames** -- a trot whose planted
    paw moves up and down floats and sinks
  * **the head is byte-identical across frames**, found at exactly one row offset
    per frame when scanning every row AND every column placement, always dx == 0
  * the four frames change by a similar number of pixels per step
  * **every pixel facing transparency is outline**, with one documented exception
  * the rendered PNG and GIF decode back to the grids
"""

import sys
from pathlib import Path

from PIL import Image

from gamepalette import GAME_PALETTE
from pixelkit import check_grid, report_separation
import mechdog
from mechdog import FRAMES, GROUND_ROW, HELM, H, W

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"

# A pixel on the grid's own bottom row faces the ground, not transparency, so it
# is allowed to be a fill tone. The 20x14 dog does the same -- its ground row is
# `KSSSKSSSK`. Everything else facing a gap must be outline.
GROUND_CONTACT_EXEMPT = True


def outline_defects(grid) -> list:
    h, w = len(grid), len(grid[0])
    bad = []
    for y in range(h):
        for x in range(w):
            c = grid[y][x]
            if c in (".", "K"):
                continue
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < w and 0 <= ny < h:
                    if grid[ny][nx] == ".":
                        bad.append(((x, y), c))
                        break
                elif ny >= h and GROUND_CONTACT_EXEMPT:
                    continue                      # faces the ground
                else:
                    bad.append(((x, y), c))       # faces off the canvas
                    break
    return bad


def find_block(grid, block):
    """Offsets at which `block` matches, scanning rows and columns."""
    hits = []
    bh, bw = len(block), len(block[0])
    for oy in range(len(grid) - bh + 1):
        for ox in range(len(grid[0]) - bw + 1):
            if all(grid[oy + r][ox:ox + bw] == block[r] for r in range(bh)):
                hits.append((ox, oy))
    return hits


def main() -> int:
    problems, report = [], []

    # -- shape ------------------------------------------------------------
    for i, g in enumerate(FRAMES):
        report.append(f"frame {i:<2} size : {len(g)}x{len(g[0])}")
    if len(FRAMES) != 4:
        problems.append(f"expected 4 frames, got {len(FRAMES)}")
    for i, g in enumerate(FRAMES):
        if len(g) != H or len(g[0]) != W:
            problems.append(f"frame {i}: expected {W}x{H}")
        problems += check_grid(g, f"mechdog f{i}", GAME_PALETTE)
    report.append(f"grid        : {len(FRAMES)} frames of {W}x{H}, palette-closed, "
                  f"one connected body each")

    # -- colour -----------------------------------------------------------
    # Report the tightest pair that is actually marginal. Printing the tightest by
    # raw dE is misleading: K-g sits at dE 9.3 but clears easily on lightness
    # ratio, so "tightest pair dE=9.3 against a floor of 24" reads like a failure
    # that is not there.
    fails_all, warns = [], []
    for i, g in enumerate(FRAMES):
        fails, rows = report_separation(g, f"mechdog f{i}", palette=GAME_PALETTE)
        problems += list(fails)
        fails_all += list(fails)
        warns += [r for r in rows if not r[0]]
    if warns:
        _, a, b, d, dl, floor, kind = min(warns, key=lambda r: r[3] - r[5])
        report.append(f"separation  : {len(fails_all)} hard failure(s); "
                      f"tightest marginal {a}-{b} dE={d:.1f} (floor {floor:.0f}, {kind})")
    else:
        report.append(f"separation  : {len(fails_all)} hard failure(s); "
                      f"no marginal pairs at all")

    # -- ground row -------------------------------------------------------
    lows = [max(y for y in range(len(g)) if any(c != "." for c in g[y]))
            for g in FRAMES]
    if len(set(lows)) != 1 or lows[0] != GROUND_ROW:
        problems.append(f"ground rows are {lows}, expected all {GROUND_ROW}")
    else:
        report.append(f"ground row  : row {GROUND_ROW} in all {len(FRAMES)} frames")

    # -- head lock --------------------------------------------------------
    offsets = []
    for i, g in enumerate(FRAMES):
        hits = find_block(g, HELM)
        if len(hits) != 1:
            problems.append(f"frame {i}: helmet matched {len(hits)} times, expected 1")
            offsets.append(None)
            continue
        ox, oy = hits[0]
        offsets.append(oy)
        if ox != 16:
            problems.append(f"frame {i}: helmet at column {ox}, expected 16 (drift)")
    report.append(f"head offs   : {offsets}  (whole rows only, dx == 0)")
    if offsets != [1, 0, 1, 0]:
        problems.append(f"head row offsets are {offsets}, expected [1, 0, 1, 0]")

    # -- rhythm -----------------------------------------------------------
    steps = [sum(1 for y in range(H) for x in range(W)
                 if FRAMES[i][y][x] != FRAMES[(i + 1) % len(FRAMES)][y][x])
             for i in range(len(FRAMES))]
    report.append(f"changed px  : {steps} (last entry is the loop wrap)")
    if max(steps) > 2.5 * max(1, min(steps)):
        problems.append(f"uneven rhythm: {steps}")

    # -- outline ----------------------------------------------------------
    for i, g in enumerate(FRAMES):
        od = outline_defects(g)
        if od:
            problems.append(f"frame {i}: {len(od)} pixel(s) facing transparency "
                            f"without an outline: {od[:5]}")
    report.append("outline     : every pixel facing a gap is K "
                  "(bottom row exempt: it faces the ground)")

    # -- rendered assets --------------------------------------------------
    prev = ASSETS / "mechdog_preview.png"
    if not prev.exists():
        problems.append("mechdog_preview.png is missing - run mechdog.py first")
    else:
        img = Image.open(prev).convert("RGBA")
        sx, sy = mechdog.PAD, mechdog.PAD
        bad = 0
        for i, g in enumerate(FRAMES):
            ox = sx + i * (W * mechdog.SCALE + mechdog.PAD)
            for y in range(H):
                for x in range(W):
                    px = img.getpixel((ox + x * mechdog.SCALE + 1,
                                       sy + y * mechdog.SCALE + 1))
                    want = GAME_PALETTE[g[y][x]]
                    if g[y][x] == ".":
                        want = (*mechdog.BG[:3], 255)
                    if px[:3] != want[:3]:
                        bad += 1
        if bad:
            problems.append(f"mechdog_preview.png: {bad} pixel(s) do not match the grids")
        else:
            report.append("preview     : ok - every frame decodes back pixel for pixel")

    gif = ASSETS / "mechdog.gif"
    if not gif.exists():
        problems.append("mechdog.gif is missing")
    else:
        im = Image.open(gif)
        if im.n_frames != len(FRAMES):
            problems.append(f"mechdog.gif has {im.n_frames} frames, expected {len(FRAMES)}")
        elif im.info.get("loop") != 0:
            problems.append("mechdog.gif does not loop")
        else:
            report.append(f"gif         : ok - {im.n_frames} frames, "
                          f"{im.info.get('duration')}ms, loops")

    print("-- mechpup ----------------------------------------------")
    for line in report:
        print(f"  {line}")
    for p in problems:
        print(f"  FAIL  {p}")
    if not problems:
        print("  ok    sized, grounded, head-locked, outlined, and it renders")
    print(f"\n  failures : {len(problems)}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
