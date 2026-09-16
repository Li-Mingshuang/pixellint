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
    """Return an ordered list of (key, grid)."""
    items = []

    def add(prefix, name, value):
        # A grid is list[str]. A clip is list[grid], i.e. list[list[str]].
        # Getting this backwards silently iterates the grid's ROWS as if they
        # were frames, which then blow up deep inside build().
        if isinstance(value, list) and value and isinstance(value[0], str):
            items.append((f"{prefix}.{name}", value))          # a single grid
        elif isinstance(value, list) and value and isinstance(value[0], list) \
                and value[0] and isinstance(value[0][0], str):
            for i, frame in enumerate(value):
                items.append((f"{prefix}.{name}.{i}", frame))
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
            for i, g in enumerate(frames):
                items.append((f"player.{clip}.{i}", g))
    except Exception as exc:
        print(f"  ! player unavailable: {exc}")

    try:
        import zombie as zb
        for clip, frames in zb.ZOMBIE.items():
            for i, g in enumerate(frames):
                items.append((f"zombie.{clip}.{i}", g))
    except Exception as exc:
        print(f"  ! zombie unavailable: {exc}")

    try:
        import effects as fx
        for name, val in fx.FX.items():
            add("fx", name, val)
    except Exception as exc:
        print(f"  ! effects unavailable: {exc}")

    return items


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
    atlas, anchors = {}, {}
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
    return sheet, atlas, anchors


def main() -> int:
    items = collect()
    if not items:
        print("no art modules found - nothing to pack")
        return 1

    sheet, atlas, anchors = pack(items)
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
