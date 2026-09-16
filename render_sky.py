"""Render the sky grids to PNG so a human can inspect them.

    python render_sky.py

Writes three files into assets/:

  sky_backdrop_native.png   160x58   the backdrop, pixel for pixel
  sky_clouds_native.png      64x12   one cloud tile, alpha intact
  sky_preview.png                    proof sheet: the backdrop at 3x, beside it
                                     the cloud band tiled 3x at 3x on the sky
                                     tone with a tick over each tile boundary so
                                     the wrap is inspectable, and below it the
                                     tiled band composited onto the backdrop's
                                     sky -- the way it will actually be seen.

One character of the grid is one pixel: this script only scales, it never
redraws, so the PNGs cannot drift from sky.py.
"""

from pathlib import Path

from PIL import Image, ImageDraw

from pixelkit import SCENE_PALETTE, build, preview

from sky import BACKDROP, CLOUD_STRIP

OUT_DIR = Path(__file__).resolve().parent / "assets"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SCALE = 3
PAD = 12
SHEET_BG = (30, 32, 40, 255)
CLOUD_ROW = 2          # where the band sits when composited onto the backdrop


def tile_times(grid, times):
    return [row * times for row in grid]


def tile_to_width(grid, width):
    row0 = grid[0]
    times = -(-width // len(row0))
    return [r * times for r in grid]


def main() -> None:
    backdrop = build(BACKDROP)
    clouds = build(CLOUD_STRIP)
    band = build(tile_times(CLOUD_STRIP, 3))                     # 192 x 12
    over = backdrop.copy()
    over.alpha_composite(build(tile_to_width(CLOUD_STRIP, backdrop.width)), (0, CLOUD_ROW))

    bg_backdrop = preview(backdrop, SCALE)
    bg_over = preview(over, SCALE)
    bg_band = preview(band, SCALE, bg=SCENE_PALETTE["A"][:3])    # sky tone behind

    sheet = Image.new("RGBA", (PAD * 3 + bg_backdrop.width + bg_band.width,
                               PAD * 3 + bg_backdrop.height + bg_over.height), SHEET_BG)
    sheet.alpha_composite(bg_backdrop, (PAD, PAD))
    sheet.alpha_composite(bg_over, (PAD, PAD + bg_backdrop.height + PAD))
    band_x = PAD + bg_backdrop.width + PAD
    sheet.alpha_composite(bg_band, (band_x, PAD))

    # tick marks over each tile boundary, drawn in the margin so the art itself
    # is untouched: the wrap is exactly where the ticks are.
    draw = ImageDraw.Draw(sheet)
    for k in range(1, 3):
        x = band_x + k * len(CLOUD_STRIP[0]) * SCALE
        draw.rectangle([x - 1, PAD - 6, x, PAD - 2], fill=(232, 200, 74, 255))

    backdrop.save(OUT_DIR / "sky_backdrop_native.png")
    clouds.save(OUT_DIR / "sky_clouds_native.png")
    sheet.save(OUT_DIR / "sky_preview.png")

    print("backdrop  : %dx%d native, %d colours" % (backdrop.width, backdrop.height,
                                                    len({c for r in BACKDROP for c in r})))
    print("cloud band: %dx%d native (3 tiles = %d px), %d opaque px per tile"
          % (clouds.width, clouds.height, band.width,
             sum(1 for r in CLOUD_STRIP for c in r if c != ".")))
    for name in ("sky_backdrop_native.png", "sky_clouds_native.png", "sky_preview.png"):
        print("wrote     : %s" % (OUT_DIR / name))


if __name__ == "__main__":
    main()
