"""Verification for the combat effects (``game/effects.py``).

Pixel art is deterministic, and so is the difference between a muzzle flash and
a yellow blob.  Everything this module claims is asserted here rather than
eyeballed:

  * structure  - the exact size stated in the brief for every frame of every
                 effect, palette-only, and no ragged rows
  * body       - muzzle/bullet/casing/bloodpool are ONE 4-connected component
                 in every frame; blood/gib/impact/dust are allowed to break up,
                 so they are held to a component budget instead, and at least
                 one of their frames must actually have separated pieces
  * flash      - the muzzle flash grows and collapses: frame 2 > frame 1 >
                 frame 3 >= frame 4 in opaque pixels, and frame 4 is fully
                 transparent (a 40 ms flash ends on an empty frame -- that
                 ``check_grid`` note is expected here, not worked around)
  * grounding  - the blood pool's lowest opaque row IS its last row, so the
                 caller can sit it on GROUND_Y with no offset
  * readability- dE76 for every touching colour pair, against GAME_PALETTE
  * the raster - fx_preview.png decodes back to these grids pixel for pixel,
                 and fx_muzzle.gif is 4 x 40 ms that plays ONCE

    python game/check_effects.py

Exits non-zero if anything fails.
"""

from pathlib import Path
import sys

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
for _path in (str(_ROOT), str(_HERE)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from effects import (
    BG,
    MUZZLE_MS,
    SCALE,
    any_grids,
    components,
    frames_of,
    FX,
    opaque_count,
    preview_layout,
)
from gamepalette import GAME_PALETTE
from pixelkit import check_grid, report_separation

# Sizes are stated here rather than imported, so a typo in effects.py cannot
# quietly redefine the contract it is checked against.
EXPECTED = {
    "muzzle": [(16, 12)] * 4,
    "bullet": [(10, 4)] * 2,
    "casing": [(5, 4)] * 2,
    "impact": [(10, 10)] * 3,
    "blood": [(8, 8), (8, 10), (10, 8)],
    "bloodpool": [(20, 8)],
    "gib": [(4, 4), (3, 3), (3, 3)],
    "dust": [(12, 8)] * 3,
}

CONNECTED = ("muzzle", "bullet", "casing", "bloodpool")
LOOSE = ("blood", "impact", "dust")   # must actually break into separate pieces
SOLID = ("gib",)                      # a gib is one lump, so exactly one part

# Component budget for the effects that are meant to break up.  A 1px spark or
# droplet is a component; a *hundred* of them in a 10x10 would be noise, not a
# spray, so each effect caps how far it may shatter.  Everything except the main
# body has to be a speck: if a "separated droplet" is 9px it is a second blob,
# which is exactly the failure this catches.
MAX_COMPONENTS = {"blood": 8, "impact": 16, "dust": 20}
MAX_SATELLITE_PX = 4

MUZZLE_GROWTH = "frame 2 > frame 1 > frame 3 >= frame 4"
GIF_SIZE = (16 * SCALE, 12 * SCALE)


def structure_problems() -> tuple[list[str], list[str]]:
    problems, report = [], []
    if sorted(FX) != sorted(EXPECTED):
        problems.append(f"FX keys are {sorted(FX)}, expected {sorted(EXPECTED)}")
        return problems, report

    total = 0
    for name, sizes in EXPECTED.items():
        grids = frames_of(FX[name])
        if len(grids) != len(sizes):
            problems.append(f"{name}: {len(grids)} frame(s), expected {len(sizes)}")
            continue
        for i, (grid, (w, h)) in enumerate(zip(grids, sizes)):
            total += 1
            if len(grid) != h or any(len(r) != w for r in grid):
                problems.append(
                    f"{name} f{i}: grid is {len(grid[0])}x{len(grid)}, expected {w}x{h}")
                continue
            notes = check_grid(grid, f"{name} f{i}", palette=GAME_PALETTE)
            if name == "muzzle" and i == 3:
                # Documented: the burnt-out frame is transparent on purpose.
                if notes != [f"{name} f{i}: fully transparent"]:
                    problems.append(f"{name} f{i}: expected only the transparent note, got {notes}")
                else:
                    report.append(f"{name} f{i}          : fully transparent (expected)")
                continue
            if name in LOOSE:
                # separate sparks/droplets/chunks are the point here
                notes = [n for n in notes if "floating pixel" not in n]
            problems += notes
        cells = " ".join(f"{len(g[0])}x{len(g)}" for g in grids)
        report.append(f"{name:<10} size   : {len(grids)} frame(s), {cells}")
    report.append(f"grids checked     : {total}")
    return problems, report


def body_problems() -> tuple[list[str], list[str]]:
    """One body where it must be, a sane component budget where it need not be."""
    problems, report = [], []
    for name in CONNECTED:
        for i, grid in enumerate(frames_of(FX[name])):
            if not any(ch != "." for row in grid for ch in row):
                # the burnt-out muzzle frame; structure_problems reports it
                continue
            comps = components(grid)
            if len(comps) != 1:
                problems.append(
                    f"{name} f{i}: {len(comps)} components, expected exactly 1 connected body")
    report.append(f"single body       : {', '.join(CONNECTED)} - connected in every lit frame")

    for name in SOLID:
        for i, grid in enumerate(frames_of(FX[name])):
            comps = components(grid)
            if len(comps) != 1:
                problems.append(f"{name} f{i}: {len(comps)} components, a chunk must be one lump")
        report.append(f"{name:<10} parts  : one solid lump per frame, as intended")

    for name in LOOSE:
        counts, bodies, split_frames = [], [], 0
        for i, grid in enumerate(frames_of(FX[name])):
            comps = sorted(components(grid), key=len, reverse=True)
            sizes = [len(c) for c in comps]
            counts.append(len(comps))
            bodies.append(sizes[0] if sizes else 0)
            if len(comps) > 1:
                split_frames += 1
            if len(comps) > MAX_COMPONENTS[name]:
                problems.append(
                    f"{name} f{i}: {len(comps)} components, over the {MAX_COMPONENTS[name]} budget")
            for s in sizes[1:]:
                if s > MAX_SATELLITE_PX:
                    problems.append(
                        f"{name} f{i}: a {s}px separated piece, over the {MAX_SATELLITE_PX}px "
                        f"speck cap - that is a second blob, not a droplet")
        if split_frames == 0:
            problems.append(f"{name}: no frame has separated pieces, but it is meant to break up")
        report.append(
            f"{name:<10} parts  : components per frame {counts}, body {bodies}px, "
            f"specks <= {MAX_SATELLITE_PX}px, budget {MAX_COMPONENTS[name]}")
    return problems, report


def muzzle_problems() -> tuple[list[str], list[str]]:
    problems, report = [], []
    grids = frames_of(FX["muzzle"])
    counts = [opaque_count(g) for g in grids]
    report.append(f"muzzle flash      : {counts} opaque px per frame ({MUZZLE_GROWTH})")

    if counts[1] <= counts[0]:
        problems.append(f"muzzle: full bloom ({counts[1]}px) is not bigger than the core ({counts[0]}px)")
    if counts[0] <= counts[2]:
        problems.append(f"muzzle: the core ({counts[0]}px) is not bigger than the collapse ({counts[2]}px)")
    if counts[2] < counts[3]:
        problems.append(f"muzzle: the collapse ({counts[2]}px) is smaller than the empty frame ({counts[3]}px)")
    if counts[3] != 0:
        problems.append(f"muzzle: frame 4 has {counts[3]}px, expected a fully transparent frame")

    # A burst, not a blob: the bloom frame has to be wider than it is tall and
    # carry all three flash tones with W inside X inside Y.
    bloom = grids[1]
    spirit = {ch for row in bloom for ch in row}
    widths = [sum(1 for ch in row if ch != ".") for row in bloom]
    report.append(f"muzzle bloom      : widest row {max(widths)}px of {len(bloom[0])}, tones {sorted(spirit)}")
    if max(widths) < 10:
        problems.append(f"muzzle bloom: widest row is only {max(widths)}px, too tight to read as a burst")
    for tone in "WXY":
        if tone not in spirit:
            problems.append(f"muzzle bloom: missing the {tone} tone")

    # The beam must be brighter at the core than at the tips: row 6 of the
    # bloom runs Y Y X X W W W X X Y Y Y, which is a gradient and not a bar.
    beam = bloom[6]
    core = [x for x, ch in enumerate(beam) if ch == "W"]
    tips = [x for x, ch in enumerate(beam) if ch == "Y"]
    if not core or not tips or not (min(tips) < min(core) and max(tips) > max(core)):
        problems.append(f"muzzle bloom: beam {beam!r} has no W core between Y tips")
    return problems, report


def bloodpool_problems() -> tuple[list[str], list[str]]:
    problems, report = [], []
    grid = frames_of(FX["bloodpool"])[0]
    rows = [y for y in range(len(grid)) if any(ch != "." for ch in grid[y])]
    if not rows:
        return [f"bloodpool: fully transparent, there is no pool to ground"], report
    lowest = max(rows)
    report.append(
        f"blood pool        : opaque rows {min(rows)}..{lowest} of 0..{len(grid) - 1}, "
        f"{opaque_count(grid)}px")
    if lowest != len(grid) - 1:
        problems.append(
            f"bloodpool: lowest opaque row is {lowest}, must be the last row ({len(grid) - 1})")
    cols = [x for x in range(len(grid[0])) if any(grid[y][x] != "." for y in range(len(grid)))]
    if cols[0] > 2 or cols[-1] < len(grid[0]) - 3:
        problems.append(f"bloodpool: only spans columns {cols[0]}..{cols[-1]}, too narrow for a pool")
    tones = {ch for row in grid for ch in row if ch != "."}
    missing = {"U", "u", "v"} - tones
    if missing:
        problems.append(f"bloodpool: missing tone(s) {sorted(missing)}")
    return problems, report


def separation_problems() -> tuple[list[str], list[str]]:
    failures, warnings = [], 0
    for name, i, grid in any_grids():
        found, _ = report_separation(grid, f"{name} f{i}", palette=GAME_PALETTE, quiet=True)
        failures += list(found)
        warnings += len(found.warnings)
    report = [
        f"colour separation : {len(failures)} hard failure(s), {warnings} advisory warning(s) "
        f"against GAME_PALETTE"
    ]
    if not failures:
        report.append("                    every touching pair clears the fill floor")
    return failures, report


def used_colours() -> tuple[list[str], list[str]]:
    used = sorted({c for _, _, g in any_grids() for row in g for c in row if c != "."})
    unknown = [c for c in used if c not in GAME_PALETTE]
    problems = [f"palette: {unknown} are not GAME_PALETTE keys"] if unknown else []
    return problems, [f"colours used      : {len(used)} -> {used}"]


def raster_problems() -> tuple[list[str], list[str]]:
    """fx_preview.png must decode back to FX, pixel for pixel."""
    from PIL import Image

    path = _ROOT / "assets" / "fx_preview.png"
    if not path.exists():
        return [f"{path.name} is missing - run game/effects.py first"], []
    img = Image.open(path).convert("RGBA")
    width, height, placements = preview_layout()
    problems = []
    if img.size != (width, height):
        problems.append(f"fx_preview.png is {img.size}, expected {(width, height)}")

    checked = 0
    for name, i, x, y in placements:
        grid = frames_of(FX[name])[i]
        for gy, row in enumerate(grid):
            for gx, ch in enumerate(row):
                px = x + gx * SCALE + SCALE // 2
                py = y + gy * SCALE + SCALE // 2
                want = (*BG, 255) if ch == "." else GAME_PALETTE[ch]
                got = img.getpixel((px, py))
                checked += 1
                if got != want:
                    problems.append(
                        f"fx_preview.png {name} f{i} pixel ({gx},{gy}) is {got}, expected {want}")
                    if len(problems) > 8:
                        return problems, []
    return problems[:8], [
        f"fx_preview.png    : {width}x{height}, {len(placements)} frame(s), "
        f"{checked}px decoded back to the grids"
    ]


def gif_problems() -> tuple[list[str], list[str]]:
    """fx_muzzle.gif must be 4 frames at MUZZLE_MS that play exactly once."""
    from PIL import Image, ImageSequence

    path = _ROOT / "assets" / "fx_muzzle.gif"
    if not path.exists():
        return [f"{path.name} is missing - run game/effects.py first"], []
    img = Image.open(path)
    problems = []
    if getattr(img, "n_frames", 1) != 4:
        problems.append(f"fx_muzzle.gif has {getattr(img, 'n_frames', 1)} frames, expected 4")
    if img.size != GIF_SIZE:
        problems.append(f"fx_muzzle.gif is {img.size}, expected {GIF_SIZE}")
    if img.info.get("duration") != MUZZLE_MS:
        problems.append(f"fx_muzzle.gif duration is {img.info.get('duration')}ms, expected {MUZZLE_MS}ms")
    if img.info.get("loop") is not None:
        problems.append(
            f"fx_muzzle.gif carries loop={img.info.get('loop')}; a one-shot flash must not loop")

    # The frames must be the muzzle flash in order, and the last one empty.
    frames = [f.convert("RGB") for f in ImageSequence.Iterator(img)]
    lit = []
    if len(frames) == 4:
        for fi, (frame, grid) in enumerate(zip(frames, frames_of(FX["muzzle"]))):
            on = 0
            for gy, row in enumerate(grid):
                for gx, ch in enumerate(row):
                    got = frame.getpixel((gx * SCALE + SCALE // 2, gy * SCALE + SCALE // 2))
                    lit_here = got != BG
                    on += lit_here
                    if lit_here != (ch != ".") and len(problems) < 8:
                        problems.append(
                            f"fx_muzzle.gif frame {fi} pixel ({gx},{gy}) is "
                            f"{'lit' if lit_here else 'backdrop'}, expected the opposite")
            lit.append(on)
        if lit != [opaque_count(g) for g in frames_of(FX["muzzle"])]:
            problems.append(
                f"fx_muzzle.gif frames light {lit}px, expected "
                f"{[opaque_count(g) for g in frames_of(FX['muzzle'])]}")
    return problems[:8], [
        f"fx_muzzle.gif     : 4 frames, {img.info.get('duration')}ms, "
        f"no loop extension, {GIF_SIZE[0]}x{GIF_SIZE[1]}, lit px {lit}"
    ]


def main() -> int:
    problems: list[str] = []
    report: list[str] = []

    for collector in (
        structure_problems,
        used_colours,
        body_problems,
        muzzle_problems,
        bloodpool_problems,
        separation_problems,
        raster_problems,
        gif_problems,
    ):
        found, lines = collector()
        problems += found
        report += lines

    print("-- combat effects -------------------------------------------")
    for line in report:
        print(f"  {line}")
    for p in problems:
        print(f"  FAIL  {p}")
    if not problems:
        print("  ok    every frame the size it claims, one body where it needs one, "
              "flash grows then dies, pool sits on its last row")
    print(f"\n  failures : {len(problems)}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
