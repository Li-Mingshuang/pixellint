"""Integrity + readability checks for the sky backdrop and the cloud band.

The art is a character grid, so "does it read" and "does it tile" are assertions
rather than opinions:

  * structure   - exact size, palette membership, backdrop fully opaque and a
                  single connected body, sky rows sky-only, horizon rows
                  horizon-only, last row uniform so it butts onto the ground
  * readability - dE76 for every touching palette pair, against SCENE_TIERS
  * cloud tiling- the wrap column pair (63, 0) has to clear the same tier floor
                  as any real adjacency, the shape has to cross the seam with
                  real substance instead of a 1px sliver, the column profiles
                  have to line up, and tiling must not invent a new pair
  * sky ramp    - row luminance may never go backwards downward, and must step
                  in 4-6 bands rather than drifting smoothly

check_grid() reports the cloud strip's clouds as floating pixels.  That is
expected and correct: the strip is three separate clouds in a band, and
check_grid knows nothing about the horizontal wrap.  check_cloud_components()
picks that apart -- every cloud must be individually 4-connected (cyclically),
and the component pixel counts must sum to the strip's opaque pixel count.

Run after any tweak to sky.py.
"""

from pathlib import Path

from PIL import Image

from pixelkit import (
    SCENE_PALETTE,
    SCENE_TIERS,
    VALUE_STEP,
    VALUE_STEP_MIN_DE,
    adjacent_pairs,
    check_grid,
    delta_e,
    luminance,
    report_separation,
    tier,
)

from sky import BACKDROP, CLOUD_STRIP

ASSETS = Path(__file__).resolve().parent / "assets"

W, H = 160, 58          # backdrop canvas, scene rows 0..57
CW, CH = 64, 12         # cloud tile
SKY_LAST = 44           # rows 0..44 inclusive are pure sky
SKY_KEYS = {"a", "A"}
HORIZON_KEYS = {"A", "R", "r", "G", "g", "F", "f"}
MIN_BANDS, MAX_BANDS = 4, 6


def verdict(a: str, b: str):
    """Exactly the rule report_separation applies to one touching pair."""
    d = delta_e(a, b)
    kind, floor = tier(a, b, SCENE_TIERS)
    vstep = abs(luminance(a) - luminance(b))
    ok = d >= floor or (vstep >= VALUE_STEP and d >= VALUE_STEP_MIN_DE)
    return ok, d, floor, kind


def rows_of(grid, key):
    return [y for y in range(len(grid)) if any(c == key for c in grid[y])]


def cyclic_components(grid):
    """4-connected components, wrapping horizontally -- the tile as tiled."""
    h, w = len(grid), len(grid[0])
    seen, comps = set(), []
    for y in range(h):
        for x in range(w):
            if grid[y][x] == "." or (x, y) in seen:
                continue
            stack, comp = [(x, y)], []
            seen.add((x, y))
            while stack:
                cx, cy = stack.pop()
                comp.append((cx, cy))
                for nb in (((cx + 1) % w, cy), ((cx - 1) % w, cy),
                           (cx, cy + 1), (cx, cy - 1)):
                    nx, ny = nb
                    if 0 <= ny < h and grid[ny][nx] != "." and nb not in seen:
                        seen.add(nb)
                        stack.append(nb)
            comps.append(sorted(comp))
    return comps


def vertical_run(grid, x, y):
    h, a, b = len(grid), y, y
    while a - 1 >= 0 and grid[a - 1][x] != ".":
        a -= 1
    while b + 1 < h and grid[b + 1][x] != ".":
        b += 1
    return b - a + 1


def wrapped_run(grid, x, y, step):
    """How many opaque pixels run from (x, y) in direction step, across the wrap."""
    w, n = len(grid[0]), 0
    while grid[y][(x + n * step) % w] != ".":
        n += 1
        if n > w:
            break
    return n


# --------------------------------------------------------------- structure
def check_structure():
    problems, report = [], []
    if len(BACKDROP) != H or any(len(r) != W for r in BACKDROP):
        problems.append("backdrop must be %dx%d" % (W, H))
    if len(CLOUD_STRIP) != CH or any(len(r) != CW for r in CLOUD_STRIP):
        problems.append("cloud strip must be %dx%d" % (CW, CH))
    if problems:
        return problems, report

    transparent = [(x, y) for y, row in enumerate(BACKDROP)
                   for x, c in enumerate(row) if c == "."]
    if transparent:
        problems.append("backdrop has %d transparent pixel(s), must be fully "
                        "opaque: %s" % (len(transparent), transparent[:6]))
    report.append("backdrop %dx%d, fully opaque: %s"
                  % (W, H, "yes" if not transparent else "NO"))

    report.append("check_grid(BACKDROP)     -> %s" % (check_grid(BACKDROP, "backdrop") or "[] ok"))
    own = check_grid(BACKDROP, "backdrop")
    problems += own

    strip = check_grid(CLOUD_STRIP, "clouds")
    unexpected = [p for p in strip if "floating pixel" not in p]
    if unexpected:
        problems += unexpected
    report.append("check_grid(CLOUD_STRIP)  -> %s" % (strip or "[] ok"))
    report.append("                           (the floating-pixel line is the expected "
                  "one: separate clouds, no wrap in check_grid)")

    bad_sky = sorted({c for y in range(SKY_LAST + 1) for c in BACKDROP[y]} - SKY_KEYS)
    if bad_sky:
        problems.append("rows 0..%d are not sky-only: %s" % (SKY_LAST, bad_sky))
    bad_hz = sorted({c for y in range(SKY_LAST + 1, H) for c in BACKDROP[y]} - HORIZON_KEYS)
    if bad_hz:
        problems.append("rows %d..%d use non-horizon keys: %s" % (SKY_LAST + 1, H - 1, bad_hz))
    report.append("rows 0..%d sky keys %s, rows %d..%d horizon keys %s"
                  % (SKY_LAST, sorted({c for y in range(SKY_LAST + 1) for c in BACKDROP[y]}),
                     SKY_LAST + 1, H - 1,
                     sorted({c for y in range(SKY_LAST + 1, H) for c in BACKDROP[y]})))

    last = sorted(set(BACKDROP[H - 1]))
    if len(last) != 1:
        problems.append("row %d is %s -- it must be one uniform key to meet the "
                        "ground cleanly" % (H - 1, last))
    report.append("row %d (ground contact): %s" % (H - 1, "".join(last)))
    return problems, report


# ------------------------------------------------------------ readability
def check_readability():
    b_fail, b_rows = report_separation(BACKDROP, "backdrop", tiers=SCENE_TIERS)
    c_fail, c_rows = report_separation(CLOUD_STRIP, "clouds", tiers=SCENE_TIERS)
    report = ["backdrop: %d touching palette pair(s)" % len(b_rows)]
    for ok, a, b, d, v, floor, kind in b_rows:
        report.append("  %s %s-%s dE=%5.1f dL=%4.2f floor>=%.0f (%s)"
                      % ("ok  " if ok else "FAIL", a, b, d, v, floor, kind))
    report.append("clouds  : %d touching palette pair(s)" % len(c_rows))
    for ok, a, b, d, v, floor, kind in c_rows:
        report.append("  %s %s-%s dE=%5.1f dL=%4.2f floor>=%.0f (%s)"
                      % ("ok  " if ok else "FAIL", a, b, d, v, floor, kind))
    return b_fail + c_fail, report


# ------------------------------------------------------ the cloud seam
def column_extent(xs):
    """Column set of a (possibly wrapping) shape -> (count, label)."""
    if len(xs) == 1:
        return 1, str(xs[0])
    n = len(xs)
    gaps = [(((xs[(i + 1) % n] - xs[i]) % CW), i) for i in range(n)]
    biggest, i_max = max(gaps)
    start, end = xs[(i_max + 1) % n], xs[i_max]
    label = "%d..%d" % (start, end) if start <= end else "%d..63 + 0..%d (wraps)" % (start, end)
    return n, label


def check_cloud_components():
    """check_grid cannot see the wrap; prove each cloud separately instead."""
    problems, report = [], []
    comps = sorted(cyclic_components(CLOUD_STRIP), key=lambda c: -len(c))
    opaque = sum(1 for r in CLOUD_STRIP for c in r if c != ".")
    total = sum(len(c) for c in comps)
    for i, comp in enumerate(comps):
        xs = sorted({x for x, _ in comp})
        ncols, label = column_extent(xs)
        report.append("  cloud %d: %3d px, rows %d..%d, %2d cols: %s"
                      % (i + 1, len(comp), min(y for _, y in comp),
                         max(y for _, y in comp), ncols, label))
    if total != opaque:
        problems.append("cloud components sum to %d px, strip holds %d" % (total, opaque))
    if not 2 <= len(comps) <= 3:
        problems.append("expected 2-3 distinct clouds, found %d" % len(comps))
    report.insert(0, "%d distinct clouds, %d opaque px (component sum %d)"
                  % (len(comps), opaque, total))
    return problems, report


def check_seam():
    """The seam has to behave like a real adjacency, all the way round."""
    problems, report = [], []

    # 1. every row's last and first column, joined, must clear its tier floor
    joined, same = 0, 0
    for y in range(CH):
        a, b = CLOUD_STRIP[y][CW - 1], CLOUD_STRIP[y][0]
        if a == "." or b == ".":
            continue
        if a == b:
            same += 1
            continue
        joined += 1
        ok, d, floor, kind = verdict(a, b)
        report.append("  row %2d wrap %s|%s dE=%5.1f floor>=%.0f (%s) %s"
                      % (y, a, b, d, floor, kind, "ok" if ok else "FAIL"))
        if not ok:
            problems.append("seam row %d: %s-%s dE=%.1f below its %.0f floor (%s)"
                            % (y, a, b, d, floor, kind))
    report.insert(0, "wrap column pairs: 12 rows joined, %d identical join(s), "
                     "%d differing join(s) needing a dE verdict"
                  % (same, joined))

    # 2. the tile edge must not cut the shape: opaque on one side of the wrap and
    #    sky on the other is a hard vertical edge when the tile repeats
    clipped = [y for y in range(CH)
               if (CLOUD_STRIP[y][CW - 1] != ".") != (CLOUD_STRIP[y][0] != ".")]
    report.append("  rows where the wrap cuts the shape: %s" % (clipped or "none"))
    if clipped:
        problems.append("cloud is clipped at the tile edge on row(s) %s: column 63 and "
                        "column 0 must agree about being cloud" % clipped)

    # 3. no 1px sliver at the wrap -- the shape must cross with real substance
    depth = {x: sum(1 for y in range(CH) if CLOUD_STRIP[y][x] != ".")
             for x in (0, CW - 1)}
    crossing = [y for y in range(CH)
                if CLOUD_STRIP[y][CW - 1] != "." and CLOUD_STRIP[y][0] != "."]
    runs, vruns = [], []
    for y in range(CH):
        for x in (0, CW - 1):
            if CLOUD_STRIP[y][x] == ".":
                continue
            runs.append(wrapped_run(CLOUD_STRIP, x, y, 1) +
                        wrapped_run(CLOUD_STRIP, x, y, -1) - 1)
            vruns.append(vertical_run(CLOUD_STRIP, x, y))
    contiguous = crossing == list(range(crossing[0], crossing[-1] + 1))
    report.append("  seam depth col63=%d col0=%d, crossing rows=%d %s"
                  % (depth[CW - 1], depth[0], len(crossing),
                     "(contiguous)" if contiguous else "(NOT contiguous)"))
    report.append("  seam pixels: min wrapped run=%d, min vertical run=%d"
                  % (min(runs), min(vruns)))
    if depth[0] < 2 or depth[CW - 1] < 2:
        problems.append("a seam column holds fewer than 2 cloud pixels (1px sliver)")
    if len(crossing) < 2:
        problems.append("cloud crosses the seam over %d row(s); a 1px bridge is a sliver"
                        % len(crossing))
    if not contiguous:
        problems.append("seam crossing rows %s are not contiguous" % crossing)
    if min(runs) < 2 or min(vruns) < 2:
        problems.append("1px-wide cloud sliver at the wrap (min run %d, min depth %d)"
                        % (min(runs), min(vruns)))
    seam_comp = [c for c in cyclic_components(CLOUD_STRIP)
                 if (CW - 1, crossing[0]) in c]
    span = len({x for x, _ in seam_comp[0]}) if seam_comp else 0
    report.append("  cloud containing the seam: %d px, %d columns wide"
                  % (len(seam_comp[0]) if seam_comp else 0, span))
    if span < 3:
        problems.append("the cloud at the seam is only %d column(s) wide" % span)

    # 3. the silhouette must line up across the wrap, not step
    def edges(x):
        ys = [y for y in range(CH) if CLOUD_STRIP[y][x] != "."]
        return (ys[0], ys[-1]) if ys else None

    lo, hi = edges(CW - 1), edges(0)
    report.append("  profile col63 top/bottom=%s, col0 top/bottom=%s" % (lo, hi))
    if lo and hi and (abs(lo[0] - hi[0]) > 1 or abs(lo[1] - hi[1]) > 1):
        problems.append("seam profile steps: col63 %s vs col0 %s" % (lo, hi))

    # 4. tiling must not invent an adjacency the single tile never had
    tiled = [r + r for r in CLOUD_STRIP]
    new = adjacent_pairs(tiled) - adjacent_pairs(CLOUD_STRIP)
    report.append("  new palette pairs introduced by tiling: %s" % (sorted(new) or "none"))
    if new:
        problems.append("tiling introduces palette pair(s) %s" % sorted(new))

    # 5. vertical margins, so the band never needs a vertical join
    if set(CLOUD_STRIP[0]) != {"."} or set(CLOUD_STRIP[CH - 1]) != {"."}:
        problems.append("cloud strip touches its top/bottom row; keep a margin")
    report.append("  row 0 / row %d empty (no vertical join needed): %s"
                  % (CH - 1, set(CLOUD_STRIP[0]) == {"."} and set(CLOUD_STRIP[CH - 1]) == {"."}))
    return problems, report


# ------------------------------------------------------------- sky ramp
def check_ramp():
    problems, report = [], []
    means = [sum(luminance(c) for c in BACKDROP[y]) / W for y in range(SKY_LAST + 1)]

    for y in range(1, SKY_LAST + 1):
        if means[y] < means[y - 1] - 1e-9:
            problems.append("sky row %d is darker than row %d: the ramp must only "
                            "lighten downward" % (y, y - 1))
    steps = sum(1 for y in range(1, SKY_LAST + 1) if means[y] > means[y - 1] + 1e-9)
    band_tones = sorted({round(m, 6) for m in means})
    report.append("rows 0..%d row-mean luminance %.3f -> %.3f, %d strict step(s), "
                  "%d distinct band tone(s)"
                  % (SKY_LAST, means[0], means[-1], steps, len(band_tones)))
    report.append("  band edges at row(s) %s"
                  % [y for y in range(1, SKY_LAST + 1) if means[y] > means[y - 1] + 1e-9])
    if not MIN_BANDS <= len(band_tones) <= MAX_BANDS:
        problems.append("ramp has %d band tone(s), expected %d-%d"
                        % (len(band_tones), MIN_BANDS, MAX_BANDS))
    if len(band_tones) != steps + 1:
        problems.append("band tones (%d) do not match steps+1 (%d)"
                        % (len(band_tones), steps + 1))
    if means[-1] <= means[0]:
        problems.append("sky does not get lighter toward the horizon")

    # every row of a band must be tonally flat, or the ramp chatters scanline by
    # scanline instead of banding -- that is what the nested lattice buys us
    flat = all(abs(means[y] - means[y - 1]) < 1e-9 or means[y] > means[y - 1] + 1e-9
               for y in range(1, SKY_LAST + 1))
    report.append("  monotone non-decreasing downward: %s" % flat)
    for y in range(SKY_LAST + 1):
        counts = {c: BACKDROP[y].count(c) for c in SKY_KEYS}
        a_count = counts["A"]
        if a_count not in (0, 40, 80, 120, 160):
            problems.append("sky row %d has %d A pixels; the dither lattice only "
                            "allows 0/40/80/120/160, so the row is not a flat band"
                            % (y, a_count))
    return problems, report


def check_raster():
    """Any committed PNG must decode back to the authored grid, pixel for pixel."""
    problems, report = [], []
    pairs = ((ASSETS / "sky_backdrop_native.png", BACKDROP, "sky_backdrop_native.png"),
             (ASSETS / "sky_clouds_native.png", CLOUD_STRIP, "sky_clouds_native.png"))
    for path, grid, name in pairs:
        if not path.exists():
            report.append("%s not rendered yet (run render_sky.py)" % name)
            continue
        img = Image.open(path).convert("RGBA")
        inv = {v: k for k, v in SCENE_PALETTE.items()}
        decoded = ["".join(inv[img.load()[x, y]] for x in range(img.width))
                   for y in range(img.height)]
        if img.size != (len(grid[0]), len(grid)):
            problems.append("%s is %s, grid is %dx%d"
                            % (name, img.size, len(grid[0]), len(grid)))
        elif decoded != grid:
            problems.append("%s does not decode back to the grid" % name)
        else:
            report.append("%s decodes back to the grid exactly (%dx%d)"
                          % (name, img.width, img.height))
    return problems, report


def main() -> int:
    failures = []

    print("-- structure -------------------------------------------------")
    p, r = check_structure()
    for line in r:
        print("  " + line)
    for line in p:
        print("  FAIL  " + line)
    failures += p

    print("\n-- colour separation (dE76, adjacent pairs, SCENE_TIERS) -----")
    p, r = check_readability()
    for line in r:
        print("  " + line if not line.startswith("  ") else line)
    for line in p:
        print("  FAIL  " + line)
    failures += p

    print("\n-- cloud strip: components -----------------------------------")
    p, r = check_cloud_components()
    for line in r:
        print("  " + line)
    for line in p:
        print("  FAIL  " + line)
    failures += p

    print("\n-- cloud strip: seamless wrap --------------------------------")
    p, r = check_seam()
    for line in r:
        print("  " + line)
    for line in p:
        print("  FAIL  " + line)
    failures += p

    print("\n-- sky ramp --------------------------------------------------")
    p, r = check_ramp()
    for line in r:
        print("  " + line)
    for line in p:
        print("  FAIL  " + line)
    failures += p

    print("\n-- rendered assets ------------------------------------------")
    p, r = check_raster()
    for line in r:
        print("  " + line)
    for line in p:
        print("  FAIL  " + line)
    failures += p

    print()
    print("  failures: %d" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
