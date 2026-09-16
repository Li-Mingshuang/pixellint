"""Composite a gameplay GIF from the game's own draw calls.

    node game/smoke_test.mjs --dump 48
    python render_game_gif.py

`smoke_test.mjs --dump` runs the real game headlessly and records every
drawImage and fillRect it issues. This replays that list against the atlas with
PIL, so the animation in the README is the game's actual output rather than an
illustration of it.

Frames are produced at 1x and upscaled with NEAREST, so the result stays true
pixel art.
"""

import json
import sys
from pathlib import Path

from PIL import Image

from export_game_atlas import ASSETS, GAME, HERE

FRAMES = GAME / "frames.json"
SCALE = 3
FRAME_MS = 67


def load_atlas():
    src = (GAME / "assets.js").read_text(encoding="utf-8")
    # The generated file is plain `window.X = ...;` lines; pull the JSON out.
    atlas = None
    for line in src.splitlines():
        if line.startswith("window.ATLAS = "):
            atlas = json.loads(line[len("window.ATLAS = "):].rstrip(";"))
    if atlas is None:
        raise SystemExit("could not find window.ATLAS in game/assets.js")
    import base64
    import io
    for line in src.splitlines():
        if line.startswith("window.ATLAS_PNG = "):
            uri = line[len("window.ATLAS_PNG = "):].strip().rstrip(";").strip('"')
            # it is a data URI: strip everything up to and including ";base64,"
            b64 = uri.split(";base64,", 1)[1] if ";base64," in uri else uri
            b64 = b64.strip()
            b64 += "=" * (-len(b64) % 4)          # restore any stripped padding
            return Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGBA"), atlas
    raise SystemExit("could not find window.ATLAS_PNG in game/assets.js")


def parse_colour(col):
    """fillStyle may be '#rrggbb', 'rgba(...)' or a gradient object."""
    if not isinstance(col, str):
        return None
    col = col.strip()
    if col.startswith("#"):
        h = col[1:]
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        if len(h) >= 6:
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)
        return None
    if col.startswith("rgba") or col.startswith("rgb"):
        nums = col[col.index("(") + 1:col.index(")")].split(",")
        try:
            r, g, b = (int(float(n)) for n in nums[:3])
            a = int(255 * float(nums[3])) if len(nums) > 3 else 255
            return (r, g, b, a)
        except Exception:
            return None
    return None


def main() -> int:
    if not FRAMES.exists() or "--fresh" in sys.argv:
        # Self-sufficient: drive the real game headlessly to record its draws.
        import shutil
        import subprocess
        node = shutil.which("node")
        if not node:
            print("node not found and game/frames.json is missing -- cannot render")
            return 1
        print("recording frames from the game...")
        rc = subprocess.call([node, str(GAME / "smoke_test.mjs"), "--dump", "48"],
                             cwd=HERE)
        if rc != 0 or not FRAMES.exists():
            print("failed to record frames")
            return rc or 1

    sheet, atlas = load_atlas()
    frames = json.loads(FRAMES.read_text(encoding="utf-8"))

    W, H = 320, 180
    out = []
    for fr in frames:
        img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
        # fills first would be wrong in general, but the recorder preserves order
        # only within each list; replay them merged by ignoring fills that are
        # full-screen overlays until the end.
        overlays = []
        for d in fr["draws"]:
            r = atlas.get(d["key"])
            if not r:
                continue
            sx, sy, sw, sh = r
            cell = sheet.crop((sx, sy, sx + sw, sy + sh))
            img.alpha_composite(cell, (int(round(d["dx"])), int(round(d["dy"]))))
        for f in fr["fills"]:
            col = parse_colour(f.get("col"))
            if not col or col[3] == 0:
                continue
            x, y, w, h = (int(round(f[k])) for k in ("x", "y", "w", "h"))
            if w <= 0 or h <= 0:
                continue
            if w >= W and h >= H:
                overlays.append((x, y, w, h, col))       # full-screen tint/vignette
                continue
            if not (0 <= y < H and y + h > 0):
                continue
            lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            lay.paste(col, (x, y, x + max(1, w), y + max(1, h)))
            img.alpha_composite(lay)
        for x, y, w, h, col in overlays:
            lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            lay.paste(col, (max(0, x), max(0, y), min(W, x + w), min(H, y + h)))
            img.alpha_composite(lay)
        out.append(img)

    big = [f.resize((W * SCALE, H * SCALE), Image.Resampling.NEAREST).convert("RGB")
           for f in out]

    gif = ASSETS / "game.gif"
    pal = [f.convert("P", palette=Image.Palette.ADAPTIVE, colors=128) for f in big]
    pal[0].save(gif, save_all=True, append_images=pal[1:],
                duration=FRAME_MS, loop=0, optimize=False)

    strip = ASSETS / "game_strip.png"
    s = Image.new("RGB", (W * SCALE * 3 + 16, H * SCALE + 8), (18, 20, 26))
    for i in range(min(3, len(big))):
        s.paste(big[i], (4 + i * (W * SCALE + 4), 4))
    s.save(strip)

    for i in (0, len(big) // 2, len(big) - 1):
        big[i].save(ASSETS / f"game_f{i:02d}.png")

    print(f"frames    : {len(big)} at {SCALE}x -> {W * SCALE}x{H * SCALE}")
    print(f"wrote     : {gif}  ({FRAME_MS}ms, loops)")
    print(f"wrote     : {strip}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
