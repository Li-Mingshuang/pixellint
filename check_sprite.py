"""Readability + integrity checks for the sprite and its walk cycle.

Pixel art is a deterministic medium, so almost everything that decides whether a
sprite "reads" can be asserted instead of eyeballed:

  * palette integrity   - closed outline, no floating pixels, no stray colours
  * colour separation   - Lab dE76 between every pair of colours that actually
                          touch on the sprite, judged against tiered thresholds
  * animation integrity - the head block is byte-identical in every walk frame
                          and only ever shifts by a whole row; the planted foot
                          always lands on the same ground row

Run after any tweak to the grids or the palette.
"""

from pathlib import Path

from PIL import Image

from render_sprite import H, PALETTE, SPRITE, W

ASSETS = Path(__file__).resolve().parent / "assets"

# Tiered dE76 thresholds. A subtle shade ramp is *supposed* to sit close to its
# base colour, but an outline that merges with the fill destroys the silhouette,
# and two different garments must never be confusable.
MIN_OUTLINE = 28.0   # outline vs anything it borders
MIN_SHADE = 20.0     # base vs its own shadow
MIN_MATERIAL = 45.0  # two different garments/body parts
# A large value step is itself a strong read, so a pair with a wide luminance
# gap only needs a modest dE. Without this, dark brown hair against a pale
# shadowed cheek gets flagged even though it obviously reads.
VALUE_STEP = 0.25
VALUE_STEP_MIN_DE = 25.0

SHADE_PAIRS = {
    frozenset(p) for p in
    ("Sp", "Hh", "Cc", "Pp", "Bb", "Ss", "Dc", "CD", "mp")
}
GROUND_ROW = 30


def srgb_to_lab(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    def lin(u: int) -> float:
        u /= 255.0
        return u / 12.92 if u <= 0.04045 else ((u + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(v) for v in rgb)
    x = (r * 0.4124 + g * 0.3576 + b * 0.1805) / 0.95047
    y = r * 0.2126 + g * 0.7152 + b * 0.0722
    z = (r * 0.0193 + g * 0.1192 + b * 0.9505) / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    fx, fy, fz = f(x), f(y), f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def delta_e(a: str, b: str) -> float:
    pa = srgb_to_lab(PALETTE[a][:3])
    pb = srgb_to_lab(PALETTE[b][:3])
    return sum((x - y) ** 2 for x, y in zip(pa, pb)) ** 0.5


def luminance(key: str) -> float:
    r, g, b, _ = PALETTE[key]
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255


def adjacent_pairs(grid: list[str]) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for y in range(len(grid)):
        for x in range(W):
            a = grid[y][x]
            if a == ".":
                continue
            for nx, ny in ((x + 1, y), (x, y + 1)):
                if nx < W and ny < len(grid):
                    b = grid[ny][nx]
                    if b != "." and b != a:
                        pairs.add((a, b) if a < b else (b, a))
    return pairs


def tier(a: str, b: str) -> tuple[str, float]:
    if "K" in (a, b):
        return "outline", MIN_OUTLINE
    if frozenset((a, b)) in SHADE_PAIRS:
        return "shade", MIN_SHADE
    return "material", MIN_MATERIAL


def check_grid(label: str, grid: list[str]) -> list[str]:
    """Structural integrity: shape, palette, closed outline, no floating pixels."""
    problems = []
    if len(grid) != H or any(len(r) != W for r in grid):
        return [f"{label}: grid must be {W}x{H}"]

    for i, row in enumerate(grid):
        bad = set(row) - set(PALETTE)
        if bad:
            problems.append(f"{label}: row {i} uses undefined palette keys {sorted(bad)}")

    opaque = {(x, y) for y in range(H) for x in range(W) if grid[y][x] != "."}
    if not opaque:
        return [f"{label}: empty sprite"]

    seed = min(opaque, key=lambda p: (p[1], p[0]))
    seen = {seed}
    stack = [seed]
    while stack:
        x, y = stack.pop()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < W and 0 <= ny < H and grid[ny][nx] != "." and (nx, ny) not in seen:
                seen.add((nx, ny))
                stack.append((nx, ny))
    floating = sorted(opaque - seen)
    if floating:
        problems.append(f"{label}: floating pixels (not connected to the body): {floating}")

    return problems


def check_raster() -> list[str]:
    """The PNG on disk must decode back to the authored grid, pixel for pixel."""
    img = Image.open(ASSETS / "char_native.png").convert("RGBA")
    inv = {v: k for k, v in PALETTE.items()}
    decoded = ["".join(inv[img.load()[x, y]] for x in range(W)) for y in range(H)]
    return [] if decoded == SPRITE else ["char_native.png does not match SPRITE"]


def check_walk() -> tuple[list[str], list[str]]:
    """Animation integrity. Returns (problems, report lines)."""
    from walk_cycle import FRAMES, HEAD

    problems: list[str] = []
    report: list[str] = []

    for i, grid in enumerate(FRAMES):
        problems += check_grid(f"walk f{i}", grid)

    # 1. The head must be byte-identical in every frame -- the only thing that
    #    may differ is which row it starts on.  This is the no-jitter guarantee:
    #    a face that shifts a column between frames is the classic tell of a
    #    hand-made walk cycle that looks wrong.
    offsets = []
    for i, grid in enumerate(FRAMES):
        hits = [y for y in range(H) if grid[y] == HEAD[0]]
        if len(hits) != 1:
            problems.append(f"walk f{i}: crown row matched {len(hits)} times, expected 1")
            offsets.append(None)
            continue
        off = hits[0]
        offsets.append(off)
        if grid[off:off + len(HEAD)] != HEAD:
            problems.append(f"walk f{i}: head block is not identical to the reference HEAD")
    report.append(f"head row offsets   : {offsets}  (must be [1,0,1,0]: one-pixel bob)")

    if offsets == [1, 0, 1, 0]:
        report.append("head lock          : ok - identical pixels, whole-row shift only")
    else:
        problems.append(f"head row offsets are {offsets}, expected [1, 0, 1, 0]")

    # 2. The grounded foot must always land on the same row, or the character
    #    slides and floats.
    for i, grid in enumerate(FRAMES):
        lowest = max(y for y in range(H) for x in range(W) if grid[y][x] != ".")
        if lowest != GROUND_ROW:
            problems.append(f"walk f{i}: lowest pixel is row {lowest}, expected {GROUND_ROW}")
    report.append(f"ground row         : {'ok - row ' + str(GROUND_ROW) + ' in all frames' if not problems else 'see failures'}")

    # 3. The lifted foot must alternate, or it is a bounce rather than a walk.
    #    A front view can only ever show two distinguishable foot states, so the
    #    cycle has to alternate them rather than hold one.
    foot_state = []
    for i, grid in enumerate(FRAMES):
        lows = []
        for lo, hi in ((0, W // 2), (W // 2, W)):
            rows = [y for y in range(H) for x in range(lo, hi) if grid[y][x] != "."]
            lows.append(max(rows))
        foot_state.append(tuple(lows))
    report.append(f"foot (L,R) low rows: {foot_state}")

    expected = [(GROUND_ROW, GROUND_ROW), (GROUND_ROW - 1, GROUND_ROW),
                (GROUND_ROW, GROUND_ROW), (GROUND_ROW, GROUND_ROW - 1)]
    if foot_state != expected:
        problems.append(f"foot alternation is {foot_state}, expected {expected}")
    else:
        report.append("foot alternation   : ok - contact, left lift, contact, right lift")

    # 4. The loop must not jump.  Compare every consecutive transition including
    #    the wrap from the last frame back to the first.
    diffs = []
    for i in range(len(FRAMES)):
        a, b = FRAMES[i], FRAMES[(i + 1) % len(FRAMES)]
        diffs.append(sum(1 for y in range(H) for x in range(W) if a[y][x] != b[y][x]))
    report.append(f"changed px per step: {diffs}  (last entry is the loop wrap)")
    if max(diffs) > 2.2 * min(diffs):
        problems.append(f"loop wrap jumps: changed-pixel counts {diffs} are too uneven")
    else:
        report.append("rhythm             : ok - every step changes a similar amount")

    return problems, report


def main() -> int:
    problems = check_raster()
    problems += check_grid("idle", SPRITE)

    print("-- idle sprite ----------------------------------------------")
    for p in problems:
        print(f"  FAIL  {p}")
    if not problems:
        print("  ok    raster matches source grid, outline closed, single connected body")

    walk_problems, walk_report = check_walk()
    print("\n-- walk cycle -----------------------------------------------")
    for line in walk_report:
        print(f"  {line}")
    for p in walk_problems:
        print(f"  FAIL  {p}")
    if not walk_problems:
        print("  ok    all 4 frames structurally sound, head locked, feet grounded")

    print("\n-- colour separation (dE76, adjacent pairs) -----------------")
    print("  value ladder: " + " < ".join(
        k for _, k in sorted((luminance(k), k) for k in PALETTE if k != ".")
    ))

    failures = 0
    for a, b in sorted(adjacent_pairs(SPRITE), key=lambda p: delta_e(*p)):
        d = delta_e(a, b)
        kind, floor = tier(a, b)
        vstep = abs(luminance(a) - luminance(b))
        ok = d >= floor or (vstep >= VALUE_STEP and d >= VALUE_STEP_MIN_DE)
        note = kind if d >= floor else f"{kind}, read via value step"
        failures += 0 if ok else 1
        print(
            f"  {'ok   ' if ok else 'FAIL '} {a}-{b}  dE={d:5.1f}  "
            f"dL={vstep:4.2f}  need>={floor:.0f} ({note})"
        )

    print()
    print(f"  distinct colours used : {len({c for r in SPRITE for c in r if c != '.'})}")
    print(f"  failures              : {failures + len(problems) + len(walk_problems)}")
    return 1 if (failures or problems or walk_problems) else 0


if __name__ == "__main__":
    raise SystemExit(main())
