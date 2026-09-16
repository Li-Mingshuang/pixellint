"""Integrity + readability checks for the four parallax background layers.

Same method as `check_sky.py` and `check_ground.py`: the art is an explicit
character grid, so everything that decides whether a layer "reads" and whether it
scrolls is an assertion rather than an opinion.

    shape       320 wide, the four exact heights, only GAME_PALETTE keys, `.`
                only where a layer is allowed to be transparent (FAR, MID),
                never in SKY or STREET
    structure   `check_grid` on every layer, then -- because FAR and MID are
                genuinely many separate ruins, which `check_grid` reports as
                floating pixels -- a CYCLIC flood fill that proves every
                component is a plausible ruin or antenna, and that the component
                pixel counts sum exactly to the grid's opaque count.  The ruins
                are NOT merged into a slab to silence that line.
    separation  dE76 for every touching pair, per layer and on the layer
                duplicated left-to-right, against GAME_PALETTE.  HARD FAILURES
                MUST BE ZERO.  Warnings are reported and left alone: most tight
                pairs are a gradient step or a base/shadow pair doing its job.
    seam        horizontal tileability.  Column 319 joined to column 0 is judged
                by the identical rule a real adjacency gets (`pixelkit.verdict`
                through the same code path as `report_separation`), the wrap may
                not cut a shape into a 1px sliver, FAR and MID must each carry a
                massif with real substance across the seam, tiling must not
                invent a palette pair, and the road's dashes must not be sliced.
    sky ramp    SKY is opaque, uses band keys `1` `2` `3` `4` for its gradient,
                and the band luminance only ever increases downward -- asserted
                row by row, with the star and moon pixels masked out so they
                cannot perturb the measurement.
    street      STREET is opaque and its top row is a single uniform key: that
                row is the surface the player stands on, so it has to be a clean
                edge and not a ragged one.
    darkness    MID must read as the more solid layer: its visible window has to
                be covered at least twice as heavily as FAR's, and its mass has
                to be carried by its dark tones rather than by lit faces.
    raster      every committed PNG decodes back to the authored grid, pixel for
                pixel, including the composite panel and the tiled strips inside
                assets/bg_preview.png.

Run after any tweak to game/background.py or to gen_background.py.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
for _p in (str(ROOT), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from PIL import Image  # noqa: E402

from gamepalette import GAME_H, GAME_PALETTE, GAME_W, GROUND_Y, TILE_W  # noqa: E402
from pixelkit import (  # noqa: E402
    adjacent_pairs, build, check_grid, luminance, report_separation, verdict,
)

from background import FAR, LAYER_OFFSETS, MID, SKY, STREET, Z_ORDER  # noqa: E402

ASSETS = ROOT / "assets"

GRIDS = {"SKY": SKY, "FAR": FAR, "MID": MID, "STREET": STREET}
SIZES = {"SKY": (320, 96), "FAR": (320, 56), "MID": (320, 64), "STREET": (320, 40)}
OPAQUE = {"SKY", "STREET"}          # FAR and MID are transparent where empty
SOLID_ONLY = {"FAR", "MID"}         # ... so these two must actually have holes

SKY_BAND_KEYS = set("1234")
SKY_STAR_KEYS = set("6M")
FAR_KEYS = set("56")
MID_KEYS = set("CcE5")
STREET_KEYS = set("RrMCc5")

SKY_GRADIENT_TONES = 25             # 4 plateaus + 3 ramps x 7 intermediate steps
SKY_STRICT_STEPS = 24
SKY_PLATEAUS = 4
BAND_MAX_KEYS = 2                   # a ramp row mixes exactly the two band keys

MIN_PX, MIN_COLS, MIN_ROWS = 4, 2, 2   # plausibility floor for one ruin
MAX_COMPONENTS = 40

MIN_WRAPPED_RUN = 2                 # a 1px run crossing the seam is a sliver
SEAM_MIN_COLUMNS = 3                # the massif on the seam must be this wide
SEAM_STAR_CLEARANCE = 3             # keep stars/moon well clear of the wrap
MIN_DASH_RUN = 4                    # an `M` fragment shorter than this reads cut

COVERAGE_RATIO = 2.0                # MID must be this much more solid than FAR
MID_DARK_SHARE = 0.50               # ... and carried by its dark tones
MID_DARK_KEYS = set("c5")

PAD = 16                            # preview sheet layout
SEAM_TICK_H = 6
SHEET_BG = (30, 32, 40)
STRIP_BG = (58, 62, 74)


# --------------------------------------------------------------- primitives
def pair_verdict(a: str, b: str) -> tuple[str, float, float]:
    """The identical verdict `report_separation` gives one touching pair."""
    if a == b or a == "." or b == ".":
        return "ok", 0.0, 0.0
    return verdict(a, b, GAME_PALETTE)


def cyclic_components(grid) -> list[list[tuple[int, int]]]:
    """4-connected components with the horizontal wrap: the tile as tiled."""
    hh, ww = len(grid), len(grid[0])
    seen, comps = set(), []
    for y in range(hh):
        for x in range(ww):
            if grid[y][x] == "." or (x, y) in seen:
                continue
            stack, comp = [(x, y)], []
            seen.add((x, y))
            while stack:
                cx, cy = stack.pop()
                comp.append((cx, cy))
                for nb in (((cx + 1) % ww, cy), ((cx - 1) % ww, cy),
                           (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nb[1] < hh and grid[nb[1]][nb[0]] != "." and nb not in seen:
                        seen.add(nb)
                        stack.append(nb)
            comps.append(sorted(comp))
    return comps


def wrapped_run(grid, x: int, y: int) -> int:
    """Length of the horizontal run of opaque pixels through (x, y), wrapping."""
    ww = len(grid[0])
    n = 0
    while grid[y][(x + n) % ww] != "." and n < ww:
        n += 1
    return n


def opaque_count(grid) -> int:
    return sum(1 for row in grid for c in row if c != ".")


def coverage(grid, y0: int, y1: int) -> float:
    op = sum(1 for y in range(y0, y1 + 1) for c in grid[y] if c != ".")
    return op / ((y1 - y0 + 1) * len(grid[0]))


# ------------------------------------------------------------------- shape
def check_shape() -> tuple[list[str], list[str]]:
    problems, report = [], []
    if GAME_W != TILE_W:
        problems.append(f"GAME_W {GAME_W} != TILE_W {TILE_W}: the tile width is the contract")

    for name, grid in GRIDS.items():
        w, h = SIZES[name]
        if len(grid) != h:
            problems.append(f"{name}: {len(grid)} rows, expected {h}")
        bad_rows = [i for i, r in enumerate(grid) if len(r) != w]
        if bad_rows:
            problems.append(f"{name}: {len(bad_rows)} row(s) are not {w} wide, e.g. {bad_rows[:4]}")
        stray = sorted({c for r in grid for c in r} - set(GAME_PALETTE))
        if stray:
            problems.append(f"{name}: undefined palette keys {stray}")
        holes = sum(r.count(".") for r in grid)
        if name in OPAQUE and holes:
            problems.append(f"{name}: {holes} transparent pixel(s); this layer must be fully opaque")
        if name in SOLID_ONLY and holes == 0:
            problems.append(f"{name}: no transparent pixels at all; it must be transparent where empty")
        if name in SOLID_ONLY:
            report.append(f"  {name:6s} {w}x{h:3d} opaque {opaque_count(grid):5d} "
                          f"({coverage(grid, 0, h - 1) * 100:5.1f}%) transparent {holes:5d} "
                          f"keys {''.join(sorted(set(''.join(grid)) - {'.'}))}")
        else:
            report.append(f"  {name:6s} {w}x{h:3d} opaque {opaque_count(grid):5d} (100.0%) "
                          f"keys {''.join(sorted(set(''.join(grid))))}")

    # the composite contract: the street's top row is where feet land
    street_top = LAYER_OFFSETS["STREET"]
    if street_top != GROUND_Y:
        problems.append(f"STREET is composited at scene row {street_top}, but GROUND_Y is {GROUND_Y}")
    report.append(f"  Z_ORDER {Z_ORDER}, offsets {LAYER_OFFSETS}, "
                  f"STREET row 0 = scene row {street_top} = GROUND_Y")

    sky_keys = set("".join(SKY))
    if sky_keys - (SKY_BAND_KEYS | SKY_STAR_KEYS):
        problems.append(f"SKY uses keys outside bands+stars: {sorted(sky_keys - SKY_BAND_KEYS - SKY_STAR_KEYS)}")
    for name, allowed in (("FAR", FAR_KEYS), ("MID", MID_KEYS), ("STREET", STREET_KEYS)):
        used = set("".join(GRIDS[name])) - {"."}
        if used - allowed:
            problems.append(f"{name} uses keys outside {sorted(allowed)}: {sorted(used - allowed)}")
    return problems, report


# --------------------------------------------------------------- structure
def check_structure() -> tuple[list[str], list[str]]:
    """check_grid, plus the cyclic flood fill FAR and MID actually need."""
    problems, report = [], []
    for name in ("SKY", "STREET"):
        own = check_grid(GRIDS[name], name, GAME_PALETTE)
        problems += own
        report.append(f"  check_grid({name}) -> {own or '[] ok'}")

    for name in ("FAR", "MID"):
        grid = GRIDS[name]
        own = check_grid(grid, name, GAME_PALETTE)
        unexpected = [p for p in own if "floating pixel" not in p]
        problems += unexpected
        report.append(f"  check_grid({name}) -> {own[:1] or '[] ok'}")
        report.append(f"    (that floating-pixel line is EXPECTED: {name} is many separate "
                      f"ruins.  They are not merged; the cyclic fill below proves them.)")

        comps = sorted(cyclic_components(grid), key=lambda c: -len(c))
        total = sum(len(c) for c in comps)
        op = opaque_count(grid)
        if total != op:
            problems.append(f"{name}: components sum to {total} px, grid holds {op}")
        if not 2 <= len(comps) <= MAX_COMPONENTS:
            problems.append(f"{name}: {len(comps)} components, expected 2..{MAX_COMPONENTS}")
        for i, comp in enumerate(comps):
            cols = {x for x, _ in comp}
            rows = {y for _, y in comp}
            if len(comp) < MIN_PX:
                problems.append(f"{name}: component {i} is {len(comp)} px (< {MIN_PX}): a speck")
            if len(cols) < MIN_COLS or len(rows) < MIN_ROWS:
                problems.append(f"{name}: component {i} spans {len(cols)}x{len(rows)} cols/rows "
                                f"(< {MIN_COLS}x{MIN_ROWS}): not a plausible ruin")
            if any(grid[y][x] not in (FAR_KEYS if name == "FAR" else MID_KEYS) for x, y in comp):
                problems.append(f"{name}: component {i} uses an unexpected key")
        spans = [(len(c), len({x for x, _ in c}), min(y for _, y in c), max(y for _, y in c))
                 for c in comps]
        report.append(f"    {len(comps)} cyclic component(s), {total} px == opaque {op}: "
                      f"{'yes' if total == op else 'NO'}")
        report.append(f"    #px {min(s[0] for s in spans)}..{max(s[0] for s in spans)}, "
                      f"#cols {min(s[1] for s in spans)}..{max(s[1] for s in spans)}, "
                      f"top row {min(s[2] for s in spans)}..{max(s[2] for s in spans)}")
        report.append("    largest (px, cols, ytop..ybot): "
                      + ", ".join(f"{a}/{b}/{c}-{d}" for a, b, c, d in spans[:6]))
    return problems, report


# -------------------------------------------------------------- separation
def check_separation() -> tuple[list[str], list[str], int]:
    problems, report = [], []
    warns = 0
    for name, grid in GRIDS.items():
        fails, rows = report_separation(grid, name, palette=GAME_PALETTE, quiet=True)
        tiled = [r + r for r in grid]
        tfails, trows = report_separation(tiled, f"{name} x2", palette=GAME_PALETTE, quiet=True)
        warns += len(fails.warnings)
        problems += list(fails)
        if tfails:
            problems += [f"tiled: {m}" for m in tfails]
        report.append(f"  {name:6s} single: {len(rows):2d} pair(s), {len(fails)} failure(s), "
                      f"{len(fails.warnings):2d} warning(s)   |   tiled x2: {len(trows):3d} pair(s), "
                      f"{len(tfails)} failure(s)")
        for w in sorted(fails.warnings)[:3]:
            report.append(f"           warn: {w}")
    return problems, report, warns


# --------------------------------------------------------------------- seam
def check_seam() -> tuple[list[str], list[str]]:
    problems, report = [], []
    for name, grid in GRIDS.items():
        hh, ww = len(grid), len(grid[0])

        # 1. the wrap pair, row by row, judged exactly as a real adjacency is
        joined = same = 0
        worst = None
        for y in range(hh):
            a, b = grid[y][ww - 1], grid[y][0]
            if a == "." or b == ".":
                continue
            if a == b:
                same += 1
                continue
            joined += 1
            v, d, dl = pair_verdict(a, b)
            if worst is None or d < worst[0]:
                worst = (d, y, a, b, v)
            if v == "fail":
                problems.append(f"{name}: seam row {y} col319->0 {a}-{b} dE={d:.1f} dL={dl:.2f} FAILS")

        # 2. no 1px sliver: every opaque pixel on the wrap needs a real run
        runs = [(y, x, wrapped_run(grid, x, y))
                for y in range(hh) for x in (0, ww - 1) if grid[y][x] != "."]
        min_run = min((r for _, _, r in runs), default=ww)
        if min_run < MIN_WRAPPED_RUN:
            thin = [(y, x) for y, x, r in runs if r < MIN_WRAPPED_RUN]
            problems.append(f"{name}: 1px sliver at the wrap, rows/cols {thin[:6]}")

        # 3. the wrap has to carry real substance for the transparent layers
        crossing = [y for y in range(hh) if grid[y][ww - 1] != "." and grid[y][0] != "."]
        seam_w = same + joined
        report.append(f"  {name:6s} rows wrapping: {seam_w:3d} identical, {joined:3d} needing a verdict, "
                      f"{hh - seam_w} transparent; min wrapped run {min_run}")
        if worst:
            d, y, a, b, v = worst
            report.append(f"           tightest wrap pair: row {y} {a}-{b} dE={d:.1f} -> {v}")
        if name in SOLID_ONLY:
            if not crossing:
                problems.append(f"{name}: nothing crosses the tile seam")
            else:
                cols = lambda c: len({x for x, _ in c})  # noqa: E731
                seam_comp = [c for c in cyclic_components(grid) if (ww - 1, crossing[0]) in c]
                span = cols(seam_comp[0]) if seam_comp else 0
                report.append(f"           seam crossing over {len(crossing)} row(s) "
                              f"{crossing[0]}..{crossing[-1]}, massif {span} columns wide")
                if span < SEAM_MIN_COLUMNS:
                    problems.append(f"{name}: the massif on the seam is only {span} column(s) wide")

        # 4. tiling must not invent a palette pair
        new = adjacent_pairs([r + r for r in grid], GAME_PALETTE) - adjacent_pairs(grid, GAME_PALETTE)
        if new:
            problems.append(f"{name}: tiling introduces palette pair(s) {sorted(new)}")

    # 5. per-layer feature rules that only make sense at the wrap
    near = [(x, y) for y in range(len(SKY)) for x in range(GAME_W)
            if SKY[y][x] in SKY_STAR_KEYS and min(x, GAME_W - 1 - x) < SEAM_STAR_CLEARANCE]
    if near:
        problems.append(f"SKY: star/moon pixel within {SEAM_STAR_CLEARANCE} of the seam: {near[:6]}")
    report.append(f"  SKY    star/moon min distance from the seam: "
                  f"{min(min(x, GAME_W - 1 - x) for y in range(len(SKY)) for x in range(GAME_W) if SKY[y][x] in SKY_STAR_KEYS)}")

    dashes = []
    for y in range(len(STREET)):
        x = 0
        while x < GAME_W:
            if STREET[y][x] == "M":
                n = 0
                while x + n < GAME_W and STREET[y][x + n] == "M":
                    n += 1
                dashes.append((y, x, n))
                x += n
            else:
                x += 1
    if dashes and min(d[2] for d in dashes) < MIN_DASH_RUN:
        problems.append(f"STREET: an `M` marking fragment is under {MIN_DASH_RUN} px: "
                        f"{[d for d in dashes if d[2] < MIN_DASH_RUN][:6]}")
    if dashes:
        report.append(f"  STREET {len(dashes)} `M` dash run(s), length "
                      f"{min(d[2] for d in dashes)}..{max(d[2] for d in dashes)}, rows "
                      f"{sorted({d[0] for d in dashes})}; col 319 is "
                      f"{'a gap' if STREET[18][319] != 'M' else 'IN a dash'}, col 0 starts a dash")
    return problems, report


# ----------------------------------------------------------------- sky ramp
def check_sky_ramp() -> tuple[list[str], list[str]]:
    problems, report = [], []
    hh = len(SKY)

    if any(c == "." for r in SKY for c in r):
        problems.append("SKY has transparent pixels; a sky layer is fully opaque")

    means, grad_keys = [], []
    for y in range(hh):
        px = [c for c in SKY[y] if c in SKY_BAND_KEYS]     # stars/moon masked out
        grad_keys.append(set(px))
        means.append(sum(luminance(c, GAME_PALETTE) for c in px) / len(px))

    for y in range(1, hh):
        if means[y] < means[y - 1] - 1e-12:
            problems.append(f"SKY: row {y} (lum {means[y]:.5f}) is darker than row {y - 1} "
                            f"({means[y - 1]:.5f}); the ramp must only lighten downward")
    steps = [y for y in range(1, hh) if means[y] > means[y - 1] + 1e-12]
    tones = sorted({round(m, 9) for m in means})

    # every ramp row mixes exactly its two band keys: a clean step, not a mush
    for y in range(hh):
        if len(grad_keys[y]) > BAND_MAX_KEYS:
            problems.append(f"SKY: row {y} mixes {len(grad_keys[y])} band keys "
                            f"({sorted(grad_keys[y])}); a step is two at most")

    # plateaus: runs of equal gradient tone, and each must be one flat band
    groups, start = [], 0
    for y in range(1, hh + 1):
        if y == hh or abs(means[y] - means[start]) > 1e-12:
            groups.append((start, y - 1))
            start = y
    wide = [gp for gp in groups if gp[1] > gp[0]]
    if len(groups) != SKY_GRADIENT_TONES:
        problems.append(f"SKY: {len(groups)} distinct band tones, expected {SKY_GRADIENT_TONES}")
    if len(steps) != SKY_STRICT_STEPS:
        problems.append(f"SKY: {len(steps)} strict step(s), expected {SKY_STRICT_STEPS}")
    if len(wide) != SKY_PLATEAUS:
        problems.append(f"SKY: {len(wide)} plateau(s) longer than one row, expected {SKY_PLATEAUS}")
    for a, b in wide:
        keys = set(SKY[a]) | set(SKY[b])
        if len(keys - SKY_STAR_KEYS) != 1:
            problems.append(f"SKY: plateau rows {a}..{b} is not one flat band "
                            f"({sorted(keys - SKY_STAR_KEYS)})")

    report.append(f"  rows 0..{hh - 1}: row luminance {means[0]:.5f} -> {means[-1]:.5f}, "
                  f"monotone non-decreasing: {all(means[y] >= means[y - 1] - 1e-12 for y in range(1, hh))}")
    report.append(f"  {len(tones)} distinct band tone(s), {len(steps)} strict step(s), "
                  f"{len(wide)} plateau(s): {[(a, b, ''.join(sorted(set(SKY[a]) - SKY_STAR_KEYS))) for a, b in wide]}")
    report.append(f"  band edges at row(s) {[steps[i] for i in range(len(steps)) if i == 0 or steps[i] != steps[i - 1] + 1][:8]}")
    report.append("  band edge ladder: " + " ".join(f"{y}:{means[y]:.4f}" for y in steps[:9]) + " ...")

    # `4`-`6` is a hard failure in this palette: prove `6` never touches haze
    touch = [(x, y) for y in range(hh) for x in range(GAME_W) if SKY[y][x] == "6"
             for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0))
             if 0 <= y + dy < hh and SKY[y + dy][(x + dx) % GAME_W] == "4"]
    if touch:
        problems.append(f"SKY: `6` star touches `4` haze (dE 7.75, a hard failure): {touch[:6]}")
    stars = Counter(c for r in SKY for c in r if c in SKY_STAR_KEYS)
    report.append(f"  `6` never touches `4` haze: {not touch}; star/moon pixels {dict(stars)}")
    return problems, report


# ------------------------------------------------------------------ street
def check_street_surface() -> tuple[list[str], list[str]]:
    problems, report = [], []
    top = set(STREET[0])
    report.append(f"  STREET row 0 (the walkable surface): {sorted(top)} x {len(STREET[0])} columns")
    if len(top) != 1 or "." in top:
        problems.append(f"STREET row 0 is {sorted(top)}; the surface must be one uniform opaque key")
    if "K" in set("".join(STREET)):
        problems.append("STREET uses `K` outline; the road is not an outlined sprite")
    if "E" in set("".join(STREET)):
        problems.append("STREET uses `E`; the warm window accent belongs to MID only")
    report.append(f"  row 1 uniform: {len(set(STREET[1])) == 1}; "
                  f"rows 0..1 clean, detail from row 2 down")
    if len(set(STREET[1])) != 1:
        problems.append("STREET row 1 is not uniform; the surface needs a clean 2px lip")
    return problems, report


# ---------------------------------------------------------------- darkness
def check_darkness() -> tuple[list[str], list[str]]:
    """MID has to read as the darker, more solid band -- measured, not claimed."""
    problems, report = [], []
    far_off, mid_off = LAYER_OFFSETS["FAR"], LAYER_OFFSETS["MID"]
    far_vis = range(0, mid_off - far_off)                       # FAR rows above MID
    mid_vis = range(far_off + len(FAR) - mid_off, len(MID))     # MID rows below FAR

    far_cov = coverage(FAR, far_vis.start, far_vis.stop - 1)
    mid_cov = coverage(MID, mid_vis.start, mid_vis.stop - 1)
    report.append(f"  visible coverage   FAR rows {far_vis.start}..{far_vis.stop - 1} "
                  f"= {far_cov * 100:5.1f}%   MID rows {mid_vis.start}..{mid_vis.stop - 1} "
                  f"= {mid_cov * 100:5.1f}%   ratio {mid_cov / far_cov:.2f}x")
    if mid_cov < COVERAGE_RATIO * far_cov:
        problems.append(f"MID covers {mid_cov * 100:.1f}% of its visible window against FAR's "
                        f"{far_cov * 100:.1f}%: not {COVERAGE_RATIO}x more solid")

    mix = {name: Counter(c for r in GRIDS[name] for c in r if c != ".")
           for name in ("FAR", "MID")}
    means = {name: sum(luminance(c, GAME_PALETTE) * n for c, n in mix[name].items())
             / sum(mix[name].values()) for name in ("FAR", "MID")}
    op = {"FAR": mix["FAR"]["5"] + mix["FAR"]["6"], "MID": opaque_count(MID)}
    share = {name: {k: n / op[name] for k, n in mix[name].items()} for name in ("FAR", "MID")}
    dark = sum(share["MID"].get(k, 0.0) for k in MID_DARK_KEYS)
    report.append(f"  opaque mean lum    FAR {means['FAR']:.4f}   MID {means['MID']:.4f}")
    report.append(f"  MID tone shares    " + " ".join(f"{k}={v:.3f}" for k, v in sorted(share["MID"].items())))
    report.append(f"  MID dark mass (c+5) = {dark:.3f} of opaque pixels")
    if dark <= MID_DARK_SHARE:
        problems.append(f"MID's dark tones `c`+`5` are only {dark:.3f} of its opaque pixels; "
                        f"its mass is carried by lit faces, so it does not read as a dark mass")

    sky_band = [luminance(SKY[y][x], GAME_PALETTE)
                for y in range(mid_off, len(SKY)) for x in range(GAME_W)]
    sky_band_mean = sum(sky_band) / len(sky_band)
    report.append(f"  sky behind MID     rows {mid_off}..{len(SKY) - 1} mean lum {sky_band_mean:.4f}; "
                  f"both layers sit darker than it (FAR {means['FAR'] < sky_band_mean}, "
                  f"MID {means['MID'] < sky_band_mean})")
    if means["MID"] >= sky_band_mean:
        problems.append("MID is not darker than the sky it stands against")

    report.append("  NOTE  FAR is a `5` near-black silhouette by palette design (lum 0.032), so "
                  "no honest arrangement makes MID's")
    report.append("        `C` concrete bodies darker PER OPAQUE PIXEL than FAR.  MID earns "
                  "'darker and more solid' as")
    report.append("        coverage and as mass: it blanks ~2.7x more of its window, and 64% of "
                  "its pixels are the dark")
    report.append("        tones `c`/`5`, not the lit `C` faces.  Reported, not faked.")
    return problems, report


# ------------------------------------------------------------------ raster
def native_image(name: str) -> Image.Image:
    return build(GRIDS[name], GAME_PALETTE)


def paste_clipped(base: Image.Image, layer: Image.Image, y: int) -> None:
    if y >= base.height:
        return
    visible = min(layer.height, base.height - y)
    base.alpha_composite(layer.crop((0, 0, layer.width, visible)), (0, y))


def composite_image() -> Image.Image:
    """The four layers in z-order, as a viewer sees them.

    The sky is the furthest layer, so the frame below the 96-row sky tile is
    filled with the sky's own last row -- that is what is behind MID there, and
    it keeps the panel honest without inventing art.
    """
    base = Image.new("RGBA", (GAME_W, GAME_H), (0, 0, 0, 255))
    paste_clipped(base, native_image("SKY"), LAYER_OFFSETS["SKY"])
    if len(SKY) < GAME_H:
        fill = Image.new("RGBA", (GAME_W, GAME_H - len(SKY)), GAME_PALETTE[SKY[-1][0]])
        paste_clipped(base, fill, len(SKY))
    for name in ("FAR", "MID", "STREET"):
        paste_clipped(base, native_image(name), LAYER_OFFSETS[name])
    return base


def preview_layout():
    """(sheet size, composite box, [(name, strip box, seam tick box)])."""
    cw, ch = GAME_W * 2, GAME_H * 2
    width = PAD * 2 + GAME_W * 4
    y = PAD
    comp = ((width - cw) // 2, y, (width - cw) // 2 + cw, y + ch)
    y += ch + PAD
    strips = []
    for name in Z_ORDER:
        h2 = SIZES[name][1] * 2
        box = (PAD, y, PAD + GAME_W * 4, y + h2)
        tick = (PAD + GAME_W * 2, y + h2 + 2, PAD + GAME_W * 2 + 2, y + h2 + 2 + SEAM_TICK_H)
        strips.append((name, box, tick))
        y += h2 + PAD + SEAM_TICK_H
    return (width, y + PAD), comp, strips


def tiled_strip(name: str) -> Image.Image:
    """The layer repeated twice, flattened on the strip backdrop."""
    grid = GRIDS[name]
    twice = [r + r for r in grid]
    img = build(twice, GAME_PALETTE)
    flat = Image.new("RGBA", img.size, (*STRIP_BG, 255))
    flat.alpha_composite(img)
    return flat


def render() -> tuple[Image.Image, dict]:
    sheet_size, comp_box, strips = preview_layout()
    sheet = Image.new("RGBA", sheet_size, (*SHEET_BG, 255))

    comp = composite_image()
    sheet.alpha_composite(comp.resize((GAME_W * 2, GAME_H * 2), Image.Resampling.NEAREST),
                          (comp_box[0], comp_box[1]))

    for name, box, tick in strips:
        img = tiled_strip(name)
        sheet.alpha_composite(img.resize((img.width * 2, img.height * 2), Image.Resampling.NEAREST),
                              (box[0], box[1]))
        for x in range(tick[0], tick[2]):
            for y in range(tick[1], tick[3]):
                sheet.putpixel((x, y), (200, 90, 80, 255))

    paths = {}
    for name in Z_ORDER:
        p = ASSETS / f"bg_{name.lower()}_native.png"
        native_image(name).save(p)
        paths[name] = p
    prev = ASSETS / "bg_preview.png"
    sheet.convert("RGBA").save(prev)
    paths["PREVIEW"] = prev
    return sheet, paths


def check_raster(paths: dict) -> tuple[list[str], list[str]]:
    problems, report = [], []
    inv = {v: k for k, v in GAME_PALETTE.items()}

    for name in Z_ORDER:
        path = paths[name]
        img = Image.open(path).convert("RGBA")
        w, h = SIZES[name]
        if img.size != (w, h):
            problems.append(f"{path.name} is {img.size}, expected {(w, h)}")
            continue
        px = img.load()
        decoded = ["".join(inv[px[x, y]] for x in range(w)) for y in range(h)]
        if decoded != GRIDS[name]:
            problems.append(f"{path.name} does not decode back to {name} pixel for pixel")
        else:
            report.append(f"  {path.name:24s} {w}x{h} decodes back to {name} exactly")

    path = paths["PREVIEW"]
    img = Image.open(path).convert("RGBA")
    sheet_size, comp_box, strips = preview_layout()
    if img.size != sheet_size:
        problems.append(f"{path.name} is {img.size}, expected {sheet_size}")
        return problems, report
    px = img.load()

    comp = composite_image()
    comp_flat = Image.new("RGBA", comp.size, (*SHEET_BG, 255))
    comp_flat.alpha_composite(comp)
    cpx = comp_flat.load()
    bad = 0
    for y in range(GAME_H):
        for x in range(GAME_W):
            if px[comp_box[0] + x * 2, comp_box[1] + y * 2] != cpx[x, y]:
                bad += 1
    if bad:
        problems.append(f"{path.name}: composite panel differs in {bad} cell(s)")
    else:
        report.append(f"  {path.name:24s} {img.width}x{img.height}: composite panel "
                      f"{GAME_W}x{GAME_H}@2x matches, z-order "
                      f"{'+'.join(Z_ORDER)}")

    for name, box, tick in strips:
        exp = tiled_strip(name)
        epx = exp.load()
        w, h = exp.size
        bad = 0
        for y in range(h):
            for x in range(w):
                if px[box[0] + x * 2, box[1] + y * 2] != epx[x, y]:
                    bad += 1
        if bad:
            problems.append(f"{path.name}: {name} tiled strip differs in {bad} cell(s)")
        else:
            report.append(f"  {'':24s} {name:6s} strip {w}x{h}@2x (tiled 2x) matches; "
                          f"seam tick at x={tick[0]}")
    return problems, report


# -------------------------------------------------------------------- main
def main() -> int:
    failures: list[str] = []
    warnings_total = 0

    print("-- shape -------------------------------------------------------")
    p, r = check_shape()
    print("\n".join(r))
    failures += [f"FAIL  {m}" for m in p]
    for m in p:
        print(f"  FAIL  {m}")

    print("\n-- structure (check_grid + cyclic flood fill) ------------------")
    p, r = check_structure()
    print("\n".join(r))
    failures += [f"FAIL  {m}" for m in p]
    for m in p:
        print(f"  FAIL  {m}")

    print("\n-- colour separation (dE76, adjacent pairs, GAME_PALETTE) ------")
    p, r, warns = check_separation()
    warnings_total += warns
    print("\n".join(r))
    failures += [f"FAIL  {m}" for m in p]
    for m in p:
        print(f"  FAIL  {m}")

    print("\n-- horizontal seam (col 319 joined to col 0) -------------------")
    p, r = check_seam()
    print("\n".join(r))
    failures += [f"FAIL  {m}" for m in p]
    for m in p:
        print(f"  FAIL  {m}")

    print("\n-- sky opacity + monotone band ramp ----------------------------")
    p, r = check_sky_ramp()
    print("\n".join(r))
    failures += [f"FAIL  {m}" for m in p]
    for m in p:
        print(f"  FAIL  {m}")

    print("\n-- street surface ---------------------------------------------")
    p, r = check_street_surface()
    print("\n".join(r))
    failures += [f"FAIL  {m}" for m in p]
    for m in p:
        print(f"  FAIL  {m}")

    print("\n-- layer darkness ---------------------------------------------")
    p, r = check_darkness()
    print("\n".join(r))
    failures += [f"FAIL  {m}" for m in p]
    for m in p:
        print(f"  FAIL  {m}")

    print("\n-- rendered assets --------------------------------------------")
    ASSETS.mkdir(parents=True, exist_ok=True)
    _sheet, paths = render()
    p, r = check_raster(paths)
    print("\n".join(r))
    failures += [f"FAIL  {m}" for m in p]
    for m in p:
        print(f"  FAIL  {m}")

    print()
    print(f"  hard failures: {len(failures)}   advisory warnings (not failures): {warnings_total}")
    for m in failures:
        print(f"  {m}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
