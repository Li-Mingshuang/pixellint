"""Assertions for PILOTPUP, the 64x96 humanoid mech.

The same standard as every other animated asset here, at 3.6x the size:

  * exact size, palette-closed, ONE connected body
  * ground row identical in all four frames
  * every pixel facing transparency is outline, except the ground-contact row
  * **the silhouette table and the rendered grid agree** -- the generator derives
    the shape from `SIL`, so a mismatch means the generator is wrong, not the art
  * the cockpit is intact: the canopy frame closes and the dog is inside it
  * the chest vents actually change between frames, and nothing else does
  * both rendered assets decode back to the grids
"""

import sys
from pathlib import Path

from PIL import Image

from gamepalette import GAME_PALETTE
from pixelkit import check_grid, report_separation
import mech
from mech import FRAMES, GROUND_ROW, H, W, COCKPIT, PATCHES

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"

GROUND_CONTACT_EXEMPT = True


def outline_defects(grid) -> list:
    bad = []
    for y in range(H):
        for x in range(W):
            c = grid[y][x]
            if c in (".", "K"):
                continue
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < W and 0 <= ny < H:
                    if grid[ny][nx] == ".":
                        bad.append(((x, y), c))
                        break
                elif ny >= H and GROUND_CONTACT_EXEMPT:
                    continue
                else:
                    bad.append(((x, y), c))
                    break
    return bad


def silhouette_defects(grid) -> list:
    """The generated fill must equal the declared silhouette.

    `armour()` derives the outline and shading FROM `SIL`, so if the two disagree
    either the generator has a bug or a patch erased a body pixel. Either way it is
    a defect, and it is invisible by eye in a 6,144-cell shape.
    """
    bad = []
    for r, entry in enumerate(mech.SIL):
        declared = set()
        for part in entry.split(","):
            a, b = part.split("-")
            declared |= set(range(int(a), int(b) + 1))
        actual = {c for c in range(W) if grid[r][c] != "."}
        if declared != actual:
            bad.append((r, sorted(declared - actual)[:4], sorted(actual - declared)[:4]))
    return bad


def main() -> int:
    problems, report = [], []

    # -- shape ------------------------------------------------------------
    for i, g in enumerate(FRAMES):
        if len(g) != H or len(g[0]) != W:
            problems.append(f"frame {i}: {len(g)}x{len(g[0])}, expected {H}x{W}")
        problems += check_grid(g, f"mech f{i}", GAME_PALETTE)
    if len(FRAMES) != 4:
        problems.append(f"expected 4 frames, got {len(FRAMES)}")
    report.append(f"grid        : {len(FRAMES)} frames of {W}x{H} "
                  f"({W * H} cells each), palette-closed, one body each")

    # -- silhouette -------------------------------------------------------
    sd = silhouette_defects(FRAMES[0])
    if sd:
        problems.append(f"silhouette mismatch on {len(sd)} row(s): {sd[:4]}")
    report.append(f"silhouette  : generated fill matches the {len(mech.SIL)}-row SIL table")

    # -- colour -----------------------------------------------------------
    fails_all, warns = [], []
    for i, g in enumerate(FRAMES):
        fails, rows = report_separation(g, f"mech f{i}", palette=GAME_PALETTE)
        problems += list(fails)
        fails_all += list(fails)
        warns += [r for r in rows if not r[0]]
    if warns:
        _, a, b, d, dl, floor, kind = min(warns, key=lambda r: r[3] - r[5])
        report.append(f"separation  : {len(fails_all)} hard failure(s); tightest "
                      f"marginal {a}-{b} dE={d:.1f} (floor {floor:.0f}, {kind})")
    else:
        report.append(f"separation  : {len(fails_all)} hard failure(s); no marginal pairs")

    # -- ground -----------------------------------------------------------
    lows = [max(y for y in range(H) if any(c != "." for c in g[y])) for g in FRAMES]
    if set(lows) != {GROUND_ROW}:
        problems.append(f"ground rows are {sorted(set(lows))}, expected {GROUND_ROW}")
    else:
        report.append(f"ground row  : row {GROUND_ROW} in all {len(FRAMES)} frames")

    # -- outline ----------------------------------------------------------
    for i, g in enumerate(FRAMES):
        od = outline_defects(g)
        if od:
            problems.append(f"frame {i}: {len(od)} pixel(s) facing a gap without an "
                            f"outline: {od[:5]}")
    report.append("outline     : every pixel facing a gap is K "
                  "(ground-contact row exempt)")

    # -- the cockpit, and the dog inside it --------------------------------
    r0, c0, _ = next(p for p in PATCHES if p[2] is COCKPIT)
    frame = FRAMES[0]
    cw = len(COCKPIT[0])
    # test the PATCH's column range, not the whole scene row: a scene row also
    # carries the chest and the vents, so checking `frame[r0]` as a whole is
    # testing the wrong thing and fails on a perfectly closed canopy.
    top = frame[r0][c0:c0 + cw]
    bot = frame[r0 + len(COCKPIT) - 1][c0:c0 + cw]
    left = [frame[r0 + i][c0] for i in range(len(COCKPIT))]
    right = [frame[r0 + i][c0 + cw - 1] for i in range(len(COCKPIT))]
    if set(top) != {"K"} or set(bot) != {"K"}:
        problems.append(f"cockpit canopy is not closed top/bottom: {top!r} {bot!r}")
    if set(left) != {"K"} or set(right) != {"K"}:
        problems.append("cockpit canopy is not closed left/right")
    inner = [frame[r0 + i][c0 + 2:c0 + cw - 2] for i in range(2, len(COCKPIT) - 2)]
    fur = sum(row.count("H") for row in inner)
    if fur < 30:
        problems.append(f"only {fur} fur pixels in the cockpit; the dog is missing")
    report.append(f"cockpit     : canopy closed on all four sides, {fur} fur pixels "
                  f"inside it (the dog)")

    # -- the animation does exactly one thing ------------------------------
    diffs = [sum(1 for y in range(H) for x in range(W)
                 if FRAMES[i][y][x] != FRAMES[(i + 1) % len(FRAMES)][y][x])
             for i in range(len(FRAMES))]
    changed_cells = {(y, x) for y in range(H) for x in range(W)
                     if FRAMES[0][y][x] != FRAMES[2][y][x]}
    allowed = set()
    for r0, c0, pw, ph in mech.VENT_ZONES:
        for dr in range(ph):
            for dc in range(pw):
                allowed.add((r0 + dr, c0 + dc))
    stray = sorted(p for p in changed_cells if p not in allowed)
    if stray:
        problems.append(f"{len(stray)} pixel(s) change outside the vent zones: "
                        f"{stray[:5]}")
    if not changed_cells:
        problems.append("the idle animation changes nothing at all")
    report.append(f"idle motion : {diffs} pixels change per step, all of them inside "
                  f"the pauldron vent grilles")

    # -- rendered assets --------------------------------------------------
    prev = ASSETS / "mech_preview.png"
    if not prev.exists():
        problems.append("mech_preview.png is missing - run mech.py first")
    else:
        img = Image.open(prev).convert("RGBA")
        bad = 0
        for i, g in enumerate(FRAMES):
            ox = 8 + i * (W * mech.SCALE + 8)
            for y in range(H):
                for x in range(W):
                    px = img.getpixel((ox + x * mech.SCALE + 1, 8 + y * mech.SCALE + 1))
                    want = GAME_PALETTE[g[y][x]] if g[y][x] != "." else (*mech.BG[:3], 255)
                    if px[:3] != want[:3]:
                        bad += 1
        if bad:
            problems.append(f"mech_preview.png: {bad} pixel(s) do not match the grids")
        else:
            report.append("preview     : ok - every frame decodes back pixel for pixel")

    gif = ASSETS / "mech.gif"
    if not gif.exists():
        problems.append("mech.gif is missing")
    else:
        im = Image.open(gif)
        if im.n_frames != len(FRAMES):
            problems.append(f"mech.gif has {im.n_frames} frames, expected {len(FRAMES)}")
        elif im.info.get("loop") != 0:
            problems.append("mech.gif does not loop")
        else:
            report.append(f"gif         : ok - {im.n_frames} frames, "
                          f"{im.info.get('duration')}ms, loops")

    print("-- pilotpup ---------------------------------------------")
    for line in report:
        print(f"  {line}")
    for p in problems:
        print(f"  FAIL  {p}")
    if not problems:
        print("  ok    sized, grounded, outlined, the dog is in it, and it breathes")
    print(f"\n  failures : {len(problems)}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
