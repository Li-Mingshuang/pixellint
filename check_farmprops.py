"""Integrity + readability checks for the six farmyard props (farmprops.py).

Same spirit as check_props.py: pixel art is deterministic, so everything that
decides whether a prop reads -- and everything that would let it float, leak a
raw fill colour into the grass, or come apart into two blobs -- is asserted
rather than eyeballed.

  * size and shape      - each grid is exactly the stated WxH, every row the
                          stated width, only SCENE_PALETTE keys
  * single body         - exactly ONE connected opaque blob, no floating pixels
  * outline coverage    - every opaque pixel that faces background (a
                          transparent neighbour, or the canvas edge) is K, so no
                          prop can leak a raw fill colour into the grass or sky
  * BASE convention     - the lowest opaque row is the grid's LAST row, so the
                          prop stands on whatever ground row it is placed
                          against, and that row is outline/background only
  * reported geometry   - the hoop / slat / board / face / tier / handle
                          constants match the pixels they claim to describe, and
                          each prop's own read (barrel bulge, crate slat rhythm,
                          signpost board overhang, stumps shoots, logpile tier
                          step, churn handles) is checked structurally
  * colour separation   - Lab dE76 for every pair of colours that actually
                          touch, with the tightest pair per prop REPORTED;
                          hard failures fail, warnings are the author's call
  * palette note        - the brief asked for an `M` highlight that
                          SCENE_PALETTE does not contain, so the churn's W
                          highlight is asserted here instead of being a silent
                          substitution
  * rendered artifact   - assets/farmprops_preview.png decodes back to the
                          authored pixels, and every prop's BASE really does
                          land on the single shared baseline

Run after any tweak to farmprops.py.
"""

from pathlib import Path

from PIL import Image

from pixelkit import SCENE_PALETTE, check_grid, report_separation, preview
from farmprops import (
    BARREL,
    BARREL_BASE_ROW,
    BARREL_FOOT_COLS,
    BARREL_H,
    BARREL_HOOP_ROWS,
    BARREL_W,
    BASES,
    CRATE,
    CRATE_BASE_ROW,
    CRATE_GAP_ROWS,
    CRATE_H,
    CRATE_SLAT_ROWS,
    CRATE_W,
    FARMPROPS,
    GRASS_BG,
    LOGPILE,
    LOGPILE_BASE_ROW,
    LOGPILE_FOOT_COLS,
    LOGPILE_H,
    LOGPILE_LOGS,
    LOGPILE_TIER_ROWS,
    LOGPILE_W,
    MILKCHURN,
    MILKCHURN_BASE_ROW,
    MILKCHURN_H,
    MILKCHURN_HANDLE_ROWS,
    MILKCHURN_NECK_ROW,
    MILKCHURN_W,
    PREVIEW_SCALE,
    SIGNPOST,
    SIGNPOST_BASE_ROW,
    SIGNPOST_BOARD_ROWS,
    SIGNPOST_CHIP_ROWS,
    SIGNPOST_H,
    SIGNPOST_POST_COLS,
    SIGNPOST_W,
    SIZES,
    STUMP,
    STUMP_BASE_ROW,
    STUMP_FACE_ROWS,
    STUMP_H,
    STUMP_SHOOT_COLS,
    STUMP_W,
    compose_preview,
    preview_layout,
    render_preview,
)

ASSETS = Path(__file__).resolve().parent / "assets"

EXPECTED_SIZES = {
    "barrel": (10, 14),
    "crate": (12, 11),
    "signpost": (8, 20),
    "stump": (12, 9),
    "logpile": (16, 10),
    "milkchurn": (8, 12),
}
EXPECTED_BASES = {"barrel": 13, "crate": 10, "signpost": 19, "stump": 8, "logpile": 9, "milkchurn": 11}

NEIGHBOURS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def opaque_cells(grid: list[str]) -> set[tuple[int, int]]:
    return {(x, y) for y, row in enumerate(grid) for x, ch in enumerate(row) if ch != "."}


def check_size(label: str, grid: list[str], w: int, h: int) -> list[str]:
    problems = []
    if (w, h) != EXPECTED_SIZES[label]:
        problems.append(f"{label}: declared size {w}x{h}, expected {EXPECTED_SIZES[label]}")
    if len(grid) != h:
        problems.append(f"{label}: {len(grid)} rows, expected {h}")
    for i, row in enumerate(grid):
        if len(row) != w:
            problems.append(f"{label}: row {i} is {len(row)} cols, expected {w}")
    bad = sorted({c for r in grid for c in r} - set(SCENE_PALETTE))
    if bad:
        problems.append(f"{label}: undefined palette keys {bad}")
    return problems


def check_single_body(label: str, grid: list[str]) -> list[str]:
    """Flood fill from the first opaque pixel: everything else is floating.

    check_grid already reports this, but the single-body rule is the one that
    decides whether a prop can be composited at all, so it is asserted here in
    its own right (and counts the components rather than just the strays).
    """
    cells = opaque_cells(grid)
    if not cells:
        return [f"{label}: fully transparent"]
    seed = min(cells, key=lambda t: (t[1], t[0]))
    seen, stack = {seed}, [seed]
    while stack:
        x, y = stack.pop()
        for dx, dy in NEIGHBOURS:
            n = (x + dx, y + dy)
            if n in cells and n not in seen:
                seen.add(n)
                stack.append(n)
    if seen != cells:
        strays = sorted(cells - seen)[:8]
        return [f"{label}: body splits -- {len(cells - seen)} pixel(s) outside the main blob: {strays}"]
    return []


def check_outline(label: str, grid: list[str]) -> list[str]:
    """Any opaque pixel facing background must be K."""
    h, w = len(grid), len(grid[0])
    leaks = []
    for y in range(h):
        for x in range(w):
            if grid[y][x] in (".", "K"):
                continue
            for dx, dy in NEIGHBOURS:
                nx, ny = x + dx, y + dy
                if not (0 <= nx < w) or not (0 <= ny < h) or grid[ny][nx] == ".":
                    leaks.append((x, y, grid[y][x]))
                    break
    if leaks:
        return [f"{label}: {len(leaks)} unoutlined silhouette pixel(s): {leaks[:8]}"]
    return []


def check_base(label: str, grid: list[str], base_row: int) -> list[str]:
    """The lowest opaque row IS the grid's last row: nothing may float."""
    h, w = len(grid), len(grid[0])
    problems = []
    opaque_rows = [y for y in range(h) if any(c != "." for c in grid[y])]
    lowest = max(opaque_rows)
    if lowest != base_row:
        problems.append(f"{label}: lowest opaque row is {lowest}, declared BASE is {base_row}")
    if base_row != h - 1:
        problems.append(f"{label}: BASE {base_row} is not the last row ({h - 1}) -- the prop floats")
    if lowest != h - 1:
        problems.append(f"{label}: lowest opaque row {lowest} is not the last row ({h - 1}) -- the prop floats")
    if not any(c == "K" for c in grid[base_row]):
        problems.append(f"{label}: BASE row has no K pixel to stand on")
    stray = sorted(set(grid[base_row]) - {".", "K"})
    if stray:
        problems.append(f"{label}: BASE row should be outline/background only, found {stray}")
    return problems


def span(grid: list[str], row: int) -> tuple[int, int | None]:
    """(first, last) opaque column of a row; last is None for an empty row."""
    cols = [x for x, ch in enumerate(grid[row]) if ch != "."]
    return (cols[0], cols[-1]) if cols else (0, None)


def check_geometry() -> list[str]:
    """Every reported constant must match the pixels it describes."""
    problems = []

    # BARREL: the hoops are iron (R/r) on their own rows, and the body bulges --
    # the middle rows are wider than both the top rim and the BASE footprint.
    for lo, hi in BARREL_HOOP_ROWS:
        for y in range(lo, hi + 1):
            if set(BARREL[y]) - {"K", "R", "r", "."}:
                problems.append(f"barrel: hoop row {y} is not iron: {BARREL[y]}")
    body = set(range(BARREL_HOOP_ROWS[0][1] + 1, BARREL_HOOP_ROWS[1][0]))
    widths = {y: span(BARREL, y)[1] - span(BARREL, y)[0] + 1 for y in body}
    if len(set(widths.values())) != 1 or max(widths.values()) != BARREL_W:
        problems.append(f"barrel: body rows do not share one full-width bulge ({widths})")
    base_w = span(BARREL, BARREL_BASE_ROW)[1] - span(BARREL, BARREL_BASE_ROW)[0] + 1
    if base_w != BARREL_FOOT_COLS[1] - BARREL_FOOT_COLS[0] + 1 or base_w >= BARREL_W:
        problems.append(f"barrel: BASE footprint {base_w}px does not match {BARREL_FOOT_COLS}")
    if body and base_w >= max(widths.values()):
        problems.append("barrel: no bulge -- the base is as wide as the waist")

    # CRATE: slat rows are wood, gap rows are one solid t band, and the two
    # alternate so the slat rhythm is actually a rhythm.
    for lo, hi in CRATE_SLAT_ROWS:
        for y in range(lo, hi + 1):
            if set(CRATE[y]) - {"K", "T", "t", "."} or CRATE[y].count("T") < 6:
                problems.append(f"crate: slat row {y} does not read as a lit board: {CRATE[y]}")
    for y in CRATE_GAP_ROWS:
        if set(CRATE[y]) - {"K", "t", "."}:
            problems.append(f"crate: gap row {y} should be solid shadow, found {sorted(set(CRATE[y]))}")
    rows = sorted([lo for lo, _ in CRATE_SLAT_ROWS] + list(CRATE_GAP_ROWS))
    if rows != sorted(set(rows)):
        problems.append("crate: slat and gap rows overlap")

    # SIGNPOST: the board spans the full grid width (so it overhangs the post on
    # both sides), and both chips really do bite a column off the post.
    lo, hi = SIGNPOST_BOARD_ROWS
    for y in range(lo, hi + 1):
        left, right = span(SIGNPOST, y)
        if (left, right) != (0, SIGNPOST_W - 1):
            problems.append(f"signpost: board row {y} spans {left}-{right}, not the full width")
    pleft, pright = SIGNPOST_POST_COLS
    for y in SIGNPOST_CHIP_ROWS:
        left, right = span(SIGNPOST, y)
        if (left, right) == (pleft, pright):
            problems.append(f"signpost: chip row {y} is not chipped")
        if grid_has(SIGNPOST, y, "K") is False:
            problems.append(f"signpost: chip row {y} is not outlined")
    if not any(spans_wood(SIGNPOST, y) for y in range(hi + 1, SIGNPOST_H)):
        problems.append("signpost: no wood below the board")

    # STUMP: the cut face is pale (U) and ringed (u), the body below it is wood,
    # and both shoots are F columns on the flanks with a K cap above them.
    # The ring's top arc is a whole row of u on purpose (row 1), so the demand is
    # that the face as a whole is pale-and-ringed and holds nothing but face
    # colour -- not that every single row carries a U.
    face = range(STUMP_FACE_ROWS[0], STUMP_FACE_ROWS[1] + 1)
    for y in face:
        if set(STUMP[y]) - {"K", "U", "u", "."}:
            problems.append(f"stump: face row {y} holds non-face colour {sorted(set(STUMP[y]) - {'K', 'U', 'u', '.'})}")
    pale_rows = [y for y in face if "U" in STUMP[y]]
    if len(pale_rows) < 2:
        problems.append(f"stump: only {len(pale_rows)} face row(s) carry the pale U")
    if not any("u" in STUMP[y] for y in face):
        problems.append("stump: cut face has no u growth ring")
    if not any("u" in STUMP[y] and "U" in STUMP[y] for y in face):
        problems.append("stump: no row shows the u ring inside the pale U face")
    if not any("T" in STUMP[y] for y in range(STUMP_FACE_ROWS[1] + 1, STUMP_BASE_ROW)):
        problems.append("stump: no wood body below the cut face")
    for col in STUMP_SHOOT_COLS:
        cols_with_f = [y for y in range(STUMP_H) if STUMP[y][col] == "F"]
        if not cols_with_f:
            problems.append(f"stump: no F shoot at col {col}")
            continue
        for y in cols_with_f:
            if STUMP[y - 1][col] not in "KF":
                problems.append(f"stump: shoot at ({col},{y}) is not capped")

    # LOGPILE: N logs in two tiers, the upper tier inset, the BASE row split
    # into the declared footprints, and every log ending in a U cut.
    upper, lower = LOGPILE_TIER_ROWS
    for lo, hi in (upper, lower):
        left, right = span(LOGPILE, lo)
        left2, right2 = span(LOGPILE, hi)
        if (left, right) != (left2, right2):
            problems.append(f"logpile: tier rows {lo}-{hi} do not share one footprint")
    if span(LOGPILE, upper[0])[0] <= span(LOGPILE, lower[0])[0]:
        problems.append("logpile: upper tier is not stepped in from the lower tier")
    base_cols = {x for x, ch in enumerate(LOGPILE[LOGPILE_BASE_ROW]) if ch != "."}
    declared = {x for lo, hi in LOGPILE_FOOT_COLS for x in range(lo, hi + 1)}
    if base_cols != declared:
        problems.append(f"logpile: BASE footprints {sorted(base_cols)} != declared {sorted(declared)}")
    if sum(r.count("U") for r in LOGPILE) < LOGPILE_LOGS:
        problems.append(f"logpile: fewer than {LOGPILE_LOGS} U cut ends "
                        f"({sum(r.count('U') for r in LOGPILE)} px of U)")

    # MILKCHURN: the neck is the narrowest row ABOVE the base course, the handle
    # rows are the widest (the tabs stick out), and the highlight is metal W.
    # Row 0 (the lid rim) is the same 4px as the neck by design -- a churn's lid
    # is as narrow as its neck -- so the neck is measured over rows 1..H-2.
    widths = {y: span(MILKCHURN, y)[1] - span(MILKCHURN, y)[0] + 1 for y in range(1, MILKCHURN_H - 1)}
    neck = min(widths, key=lambda y: widths[y])
    if neck != MILKCHURN_NECK_ROW:
        problems.append(f"milkchurn: narrowest row above the base course is {neck}, "
                        f"declared neck is {MILKCHURN_NECK_ROW}")
    if widths[MILKCHURN_NECK_ROW] >= widths[MILKCHURN_NECK_ROW - 1]:
        problems.append("milkchurn: the neck is not pinched in from the lid above it")
    for y in MILKCHURN_HANDLE_ROWS:
        if widths.get(y, 0) != MILKCHURN_W:
            problems.append(f"milkchurn: handle row {y} is {widths.get(y)}px, expected the full {MILKCHURN_W}")
        if not any(MILKCHURN[y][c] == "R" for c in (1, MILKCHURN_W - 2)):
            problems.append(f"milkchurn: handle row {y} has no metal in its tabs")
    if not any("W" in row for row in MILKCHURN):
        problems.append("milkchurn: no W highlight")
    if any("W" in MILKCHURN[y] for y in range(MILKCHURN_H - 2, MILKCHURN_H)):
        problems.append("milkchurn: the highlight must die out before the base course")

    # the brief's `M` is not a palette key -- assert the substitution is real
    if "M" in SCENE_PALETTE:
        problems.append("milkchurn: SCENE_PALETTE now defines M; re-check the highlight choice")
    if "W" not in SCENE_PALETTE:
        problems.append("milkchurn: W (the substituted highlight) is not a palette key")
    return problems


def grid_has(grid: list[str], row: int, key: str) -> bool:
    return key in grid[row]


def spans_wood(grid: list[str], row: int) -> bool:
    return bool({"T", "t"} & set(grid[row]))


def check_metadata() -> list[str]:
    problems = []
    if len(EXPECTED_SIZES) != len(FARMPROPS):
        problems.append("metadata: EXPECTED_SIZES and FARMPROPS disagree on the prop count")
    for name in FARMPROPS:
        if SIZES[name] != EXPECTED_SIZES[name]:
            problems.append(f"{name}: SIZES says {SIZES[name]}, expected {EXPECTED_SIZES[name]}")
        if BASES[name] != EXPECTED_BASES[name]:
            problems.append(f"{name}: BASES says {BASES[name]}, expected {EXPECTED_BASES[name]}")
        if BASES[name] != SIZES[name][1] - 1:
            problems.append(f"{name}: BASE {BASES[name]} is not the grid's last row")
    return problems


def check_preview() -> tuple[list[str], list[str]]:
    """The PNG on disk must decode back to the authored props, pixel for pixel.

    Rebuilds the expected image from the grids (compose_preview is what
    render_preview draws, so there is one source of truth) and compares EVERY
    pixel, grass backdrop included: a stray pixel anywhere is a failure, and so
    is a preview left stale by an edit to the grids.
    """
    problems, report = [], []
    path = ASSETS / "farmprops_preview.png"
    if not path.exists():
        path = render_preview()           # fresh checkout: build it once
        report.append("preview  was missing, rendered from farmprops.py")
    img = Image.open(path).convert("RGBA")
    width, height, baseline, xs = preview_layout()

    if img.size != (width * PREVIEW_SCALE, height * PREVIEW_SCALE):
        problems.append(f"preview: size {img.size} != {(width * PREVIEW_SCALE, height * PREVIEW_SCALE)}")
        return problems, report

    expected = preview(compose_preview(), PREVIEW_SCALE, GRASS_BG)
    if list(img.getdata()) != list(expected.getdata()):
        got, want = img.load(), expected.load()
        bad = next((x, y) for y in range(img.height) for x in range(img.width)
                   if got[x, y] != want[x, y])
        x, y = bad
        problems.append(
            f"preview: pixel ({x},{y}) is {got[x, y]}, expected {want[x, y]} "
            f"-- native ({x // PREVIEW_SCALE},{y // PREVIEW_SCALE}); re-run farmprops.py"
        )

    # every prop's BASE must sit on the one shared baseline row, and something
    # must be standing on it (not an empty gap).
    px = img.load()
    for name, grid in FARMPROPS.items():
        col = next((c for c, ch in enumerate(grid[BASES[name]]) if ch == "K"), None)
        if col is None:
            problems.append(f"{name}: BASE row has no K pixel to anchor on")
            continue
        mid = PREVIEW_SCALE // 2
        got = px[(xs[name] + col) * PREVIEW_SCALE + mid, baseline * PREVIEW_SCALE + mid]
        if got != SCENE_PALETTE["K"]:
            problems.append(f"{name}: BASE does not land on the shared baseline row (got {got})")
        above = px[(xs[name] + col) * PREVIEW_SCALE + mid, (baseline - 1) * PREVIEW_SCALE + mid]
        if above == (*GRASS_BG, 255):
            problems.append(f"{name}: nothing sits on the baseline at col {col}")

    # the grass backdrop itself must be the scene's grass tone, not a stand-in
    if px[0, img.height - 1] != (*GRASS_BG, 255):
        problems.append(f"preview: backdrop is {px[0, img.height - 1]}, not the scene grass {(*GRASS_BG, 255)}")

    report.append(f"preview  {img.size[0]}x{img.size[1]} at {PREVIEW_SCALE}x on grass, "
                  f"{len(FARMPROPS)} props on baseline native row {baseline} -> {path.name}")
    return problems, report


def main() -> int:
    problems: list[str] = []
    report: list[str] = []
    declared = {name: (FARMPROPS[name], SIZES[name][0], SIZES[name][1], BASES[name]) for name in FARMPROPS}

    print("-- structure ------------------------------------------------")
    for name, (grid, w, h, base) in declared.items():
        problems += check_size(name, grid, w, h)
        problems += check_grid(grid, name)
        problems += check_single_body(name, grid)
        problems += check_outline(name, grid)
        problems += check_base(name, grid, base)
        used = sorted({c for r in grid for c in r if c != "."})
        print(f"  {name:<9} {w:>2}x{h:<2}  base row {base}  cols {span(grid, base)[0]}-{span(grid, base)[1]}"
              f"  {len(used)} colours {' '.join(used)}")

    print("\n-- colour separation (dE76, adjacent pairs, one rule set) ---")
    tightest: dict[str, tuple] = {}
    for name, (grid, *_rest) in declared.items():
        failures, rows = report_separation(grid, name)
        problems += failures
        if rows:
            worst = min(rows, key=lambda r: r[3])
            tightest[name] = worst
            state = "ok" if worst[0] else "warn"
            print(f"  {name:<9} {len(rows):>2} touching pairs, {len(failures)} failures, "
                  f"tightest {worst[1]}-{worst[2]} dE={worst[3]:.1f} dL={worst[4]:.2f} "
                  f"({worst[6]}, need >={worst[5]:.0f}) [{state}]")

    print("\n-- reported geometry ---------------------------------------")
    problems += check_metadata()
    problems += check_geometry()
    print(f"  barrel    : hoops rows {BARREL_HOOP_ROWS[0]} and {BARREL_HOOP_ROWS[1]}, "
          f"footprint cols {BARREL_FOOT_COLS[0]}-{BARREL_FOOT_COLS[1]} ({BARREL_W}px wide)")
    print(f"  crate     : slats rows {CRATE_SLAT_ROWS}, gaps rows {CRATE_GAP_ROWS} ({CRATE_W}px wide)")
    print(f"  signpost  : post cols {SIGNPOST_POST_COLS[0]}-{SIGNPOST_POST_COLS[1]}, "
          f"board rows {SIGNPOST_BOARD_ROWS[0]}-{SIGNPOST_BOARD_ROWS[1]} (full {SIGNPOST_W}px), "
          f"chips rows {SIGNPOST_CHIP_ROWS}")
    print(f"  stump     : cut face rows {STUMP_FACE_ROWS[0]}-{STUMP_FACE_ROWS[1]}, "
          f"shoot columns {STUMP_SHOOT_COLS} ({STUMP_W}px wide)")
    print(f"  logpile   : {LOGPILE_LOGS} logs, tiers rows {LOGPILE_TIER_ROWS}, "
          f"BASE footprints {[f'{a}-{b}' for a, b in LOGPILE_FOOT_COLS]}")
    print(f"  milkchurn : neck row {MILKCHURN_NECK_ROW}, handles rows {MILKCHURN_HANDLE_ROWS} "
          f"(tabs make those rows {MILKCHURN_W}px), highlight W "
          f"({'M' not in SCENE_PALETTE and 'M is not a palette key -> W substituted' or 'M exists'})")

    print("\n-- rendered preview ---------------------------------------")
    preview_problems, preview_report = check_preview()
    problems += preview_problems
    for line in preview_report:
        print(f"  {line}")

    print("\n-- summary -------------------------------------------------")
    print(f"  {'prop':<10} {'size':<8} {'base':<5} tightest touching pair")
    for name in FARMPROPS:
        w, h = SIZES[name]
        t = tightest.get(name)
        pair = f"{t[1]}-{t[2]} dE={t[3]:.1f} dL={t[4]:.2f}" if t else "no adjacent pairs"
        print(f"  {name:<10} {f'{w}x{h}':<8} {BASES[name]:<5} {pair}")

    print()
    for p in problems:
        print(f"  FAIL  {p}")
    if not problems:
        print("  ok    all six props: exact size, palette-closed, single body, outline closed,")
        print("        lowest opaque row is the grid's last row, zero hard separation failures,")
        print("        preview decodes back to the authored pixels on one shared grass baseline")
    print(f"  failures : {len(problems)}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
