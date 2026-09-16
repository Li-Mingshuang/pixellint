"""Pack every game sprite into one atlas and emit a self-contained JS asset file.

    python export_game_atlas.py

Writes:
  assets/game_atlas.png      the packed sheet
  game/assets.js             the sheet as a base64 data URI + the atlas rects

Why a data URI: it makes the demo openable straight off the filesystem with no
server and no CORS problem, which matters for something people will double-click.

Missing art modules are skipped with a warning rather than crashing, so the game
can be developed before every layer exists.
"""

import base64
import io
import json
import sys
from pathlib import Path

from PIL import Image

from gamepalette import GAME_PALETTE
from pixelkit import build

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
GAME = HERE / "game"
ASSETS.mkdir(exist_ok=True)
GAME.mkdir(exist_ok=True)

# The art modules live in game/ and are imported by bare name.
sys.path.insert(0, str(GAME))

PAD = 1        # 1px gutter so bilinear-ish sampling can never bleed between cells
SHEET_W = 512


def collect():
    """Return (ordered [(key, grid)], {clip_prefix: frame_count})."""
    items = []
    clips = {}

    def add_clip(prefix, name, frames):
        clips[f"{prefix}.{name}"] = len(frames)
        for i, frame in enumerate(frames):
            items.append((f"{prefix}.{name}.{i}", frame))

    def add(prefix, name, value):
        # A grid is list[str]. A clip is list[grid], i.e. list[list[str]].
        # Getting this backwards silently iterates the grid's ROWS as if they
        # were frames, which then blow up deep inside build().
        if isinstance(value, list) and value and isinstance(value[0], str):
            items.append((f"{prefix}.{name}", value))          # a single grid
        elif isinstance(value, list) and value and isinstance(value[0], list) \
                and value[0] and isinstance(value[0][0], str):
            add_clip(prefix, name, value)
        elif isinstance(value, dict):
            for k, v in value.items():
                add(prefix, k, v)

    try:
        import background as bg
        for name in ("SKY", "FAR", "MID", "STREET"):
            if hasattr(bg, name):
                items.append((f"bg.{name.lower()}", getattr(bg, name)))
    except Exception as exc:
        print(f"  ! background unavailable: {exc}")

    try:
        import player as pl
        for clip, frames in pl.PLAYER.items():
            add_clip("player", clip, frames)
    except Exception as exc:
        print(f"  ! player unavailable: {exc}")

    try:
        import zombie as zb
        for clip, frames in zb.ZOMBIE.items():
            add_clip("zombie", clip, frames)
    except Exception as exc:
        print(f"  ! zombie unavailable: {exc}")

    try:
        import effects as fx
        for name, val in fx.FX.items():
            add("fx", name, val)
    except Exception as exc:
        print(f"  ! effects unavailable: {exc}")

    return items, clips


def pack(items):
    """Shelf packing. Returns (sheet, atlas, anchors).

    `anchors` records, per sprite, its lowest opaque row. The game stands
    sprites on the ground with that row rather than with the grid's height:
    a 32-row grid whose boots end on row 30 would otherwise hover two pixels
    above the street, and every frame of every clip would hover differently.
    """
    placed = []
    x = y = shelf_h = 0
    for key, grid in items:
        w, h = len(grid[0]), len(grid)
        if x + w + PAD > SHEET_W:
            x = 0
            y += shelf_h + PAD
            shelf_h = 0
        placed.append((key, grid, x, y, w, h))
        x += w + PAD
        shelf_h = max(shelf_h, h)

    sheet_h = y + shelf_h
    sheet = Image.new("RGBA", (SHEET_W, sheet_h), (0, 0, 0, 0))
    atlas, anchors, opaque = {}, {}, {}
    for key, grid, px, py, w, h in placed:
        sheet.alpha_composite(build(grid, GAME_PALETTE), (px, py))
        atlas[key] = [px, py, w, h]
        base = max((r for r in range(h) if any(c != "." for c in grid[r])), default=h - 1)
        cols = [c for r in range(h) for c, ch in enumerate(grid[r]) if ch != "."]
        first, last = (min(cols), max(cols)) if cols else (0, w - 1)
        # The rightmost opaque pixel, with its row. For a firing frame that IS the
        # barrel tip, so the game can put the muzzle flash and the bullet spawn
        # exactly where the art says the muzzle is instead of at a hand-tuned
        # offset that silently drifts the moment the art is redrawn. (It already
        # had: the hard-coded offset was two columns right and two rows above the
        # actual barrel.)
        tip_col = last
        tip_row = min((r for r in range(h) if grid[r][tip_col] != "."), default=base)
        anchors[key] = [base, first, last, tip_row, tip_col]

        # Runs of rows that are 100% opaque. A drawImage paints its whole rect
        # whether or not the pixels are transparent, so a coverage check that
        # only looks at draw rects cannot tell a filled band from a hole. This is
        # what lets the renderer be checked for holes.
        full = [r for r in range(h) if all(ch != "." for ch in grid[r])]
        if full:
            runs, start, prev = [], full[0], full[0]
            for r in full[1:]:
                if r == prev + 1:
                    prev = r
                else:
                    runs.append([start, prev]); start = prev = r
            runs.append([start, prev])
            opaque[key] = runs
    return sheet, atlas, anchors, opaque


def main() -> int:
    items, clips = collect()
    if not items:
        print("no art modules found - nothing to pack")
        return 1

    sheet, atlas, anchors, opaque = pack(items)
    sheet_path = ASSETS / "game_atlas.png"
    sheet.save(sheet_path)

    buf = io.BytesIO()
    sheet.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    js = (
        "// GENERATED by export_game_atlas.py -- do not edit by hand.\n"
        f"// {len(atlas)} sprites from {sheet.width}x{sheet.height} sheet\n"
        "// Plain globals, not ES module exports: a module script is blocked by\n"
        "// CORS over file://, and this demo is meant to be double-clickable.\n"
        f"window.ATLAS_PNG = \"data:image/png;base64,{b64}\";\n"
        f"window.ATLAS = {json.dumps(atlas, separators=(',', ':'))};\n"
        "// ANCHOR[key] = [lowestOpaqueRow, firstContentCol, lastContentCol,\n"
        "//                barrelTipRow, barrelTipCol]\n"
        "// so the game can stand a sprite on the ground, and can put the muzzle\n"
        "// flash where the art actually draws the muzzle, no matter where inside\n"
        "// the grid the art sits.\n"
        f"window.ANCHOR = {json.dumps(anchors, separators=(',', ':'))};\n"
        "// The palette as CSS colours, so the renderer can fill a region with a\n"
        "// palette tone (closing a gap between layers, tinting a flash) without\n"
        "// hard-coding a hex value that would silently drift from the art.\n"
        f"window.PALETTE = {json.dumps({k: '#%02x%02x%02x' % v[:3] for k, v in GAME_PALETTE.items() if k != '.'}, separators=(',', ':'))};\n"
        "// OPAQUE[key] = [[firstRow, lastRow], ...] runs of rows that are 100%\n"
        "// opaque. drawImage paints its whole rect regardless of alpha, so a\n"
        "// renderer coverage test cannot use draw rects alone -- this is what\n"
        "// lets it tell a filled band from a hole.\n"
        f"window.OPAQUE = {json.dumps(opaque, separators=(',', ':'))};\n"
        "// CLIPS[prefix.clip] = frame count, so the game can advance a clip by its\n"
        "// OWN length. It used to index every clip with a hard-coded % 5: with a\n"
        "// 4-frame walk that repeated frame 0 every fifth tick, and with a 2-frame\n"
        "// attack it silently fell back to the standing pose for the rest of the\n"
        "// clip -- a pose pop with no crash to announce it.\n"
        f"window.CLIPS = {json.dumps(clips, separators=(',', ':'))};\n"
    )
    js_path = GAME / "assets.js"
    js_path.write_text(js, encoding="utf-8")

    print(f"packed    : {len(atlas)} sprites into {sheet.width}x{sheet.height}")
    print(f"wrote     : {sheet_path}")
    print(f"wrote     : {js_path}  ({len(js) // 1024} KB)")
    for k in sorted(atlas)[:6]:
        print(f"    {k:<20} {atlas[k]}")
    if len(atlas) > 6:
        print(f"    ... and {len(atlas) - 6} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
