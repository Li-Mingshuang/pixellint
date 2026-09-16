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
DUMP_FRAMES = 36       # 36 x 67ms = 2.4s loop; enough to show the whole rhythm
GIF_COLOURS = 64       # 128 pushed the file past a megabyte for no visible gain


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


def _stale() -> bool:
    """True if frames.json is missing or older than the atlas it was made from.

    Recording is the expensive half (~2s), so it is cached -- but caching it
    unconditionally is how the README GIF ended up still showing a build with no
    enemies in it after the enemy art landed. The cache has to be invalidated by
    the thing it depends on.
    """
    if not FRAMES.exists():
        return True
    try:
        probe = json.loads(FRAMES.read_text(encoding="utf-8"))
        # dumps from before the interleaved-op recorder have only draws/fills and
        # cannot be replayed in order, so they must not be treated as fresh
        if probe and not any("ops" in f for f in probe):
            return True
    except Exception:
        return True
    atlas_js = GAME / "assets.js"
    if not atlas_js.exists():
        return True
    return atlas_js.stat().st_mtime > FRAMES.stat().st_mtime


def main() -> int:
    if _stale() or "--fresh" in sys.argv:
        import shutil
        import subprocess
        node = shutil.which("node")
        if not node:
            print("node not found and game/frames.json is stale -- cannot render")
            return 1
        print("recording frames from the game...")
        rc = subprocess.call([node, str(GAME / "smoke_test.mjs"), "--dump", str(DUMP_FRAMES)],
                             cwd=HERE)
        if rc != 0 or not FRAMES.exists():
            print("failed to record frames")
            return rc or 1
    else:
        print("frames.json is newer than the atlas, reusing it")

    sheet, atlas = load_atlas()
    frames = json.loads(FRAMES.read_text(encoding="utf-8"))

    W, H = 320, 180
    out = []
    for fr in frames:
        img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
        # Replay in the ORDER THE GAME ISSUED THEM. This is not a detail: the
        # first thing the renderer does is clear the frame with a full-canvas
        # fill, and an earlier version of this compositor collected full-screen
        # fills and applied them last as "overlays" -- so the clear landed on top
        # of the finished picture and flattened all 48 frames to one colour,
        # which Pillow then collapsed into a single-frame GIF.
        ops = fr.get("ops")
        if ops is None:
            # older dumps only recorded the two lists separately; approximate
            ops = ([{"kind": "draw", **d} for d in fr.get("draws", [])] +
                   [{"kind": "fill", **f} for f in fr.get("fills", [])])
        for op in ops:
            if op["kind"] == "draw":
                r = atlas.get(op["key"])
                if not r:
                    continue
                sx, sy, sw, sh = r
                img.alpha_composite(sheet.crop((sx, sy, sx + sw, sy + sh)),
                                    (int(round(op["dx"])), int(round(op["dy"]))))
                continue

            col = parse_colour(op.get("col"))
            if not col or col[3] == 0:
                continue          # gradients (muzzle light, vignette) are not replayed
            x, y = int(round(op["x"])), int(round(op["y"]))
            w, h = int(round(op["w"])), int(round(op["h"]))
            if w <= 0 or h <= 0:
                continue
            if x >= W or y >= H or x + w <= 0 or y + h <= 0:
                continue
            alpha = op.get("alpha")
            a = 1.0 if alpha is None else max(0.0, min(1.0, float(alpha)))
            lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
            lay.paste((col[0], col[1], col[2], int(col[3] * a)),
                      (max(0, x), max(0, y), min(W, x + w), min(H, y + h)))
            img.alpha_composite(lay)
        out.append(img)

    big = [f.resize((W * SCALE, H * SCALE), Image.Resampling.NEAREST).convert("RGB")
           for f in out]

    gif = ASSETS / "game.gif"
    pal = [f.convert("P", palette=Image.Palette.ADAPTIVE, colors=GIF_COLOURS) for f in big]
    pal[0].save(gif, save_all=True, append_images=pal[1:],
                duration=FRAME_MS, loop=0, optimize=False)

    strip = ASSETS / "game_strip.png"
    s = Image.new("RGB", (W * SCALE * 3 + 16, H * SCALE + 8), (18, 20, 26))
    for i in range(min(3, len(big))):
        s.paste(big[i], (4 + i * (W * SCALE + 4), 4))
    s.save(strip)

    for i in (0, len(big) // 2, len(big) - 1):
        big[i].save(ASSETS / f"game_f{i:02d}.png")

    # Remove sample frames this script wrote on an earlier run but does not write
    # now. Leaving them behind is not harmless: verify_reproducible.py compares
    # every committed asset against what the build regenerates, and a frame from
    # a 48-frame run sitting next to a 36-frame one is an asset nothing produces.
    keep = {f"game_f{i:02d}.png" for i in (0, len(big) // 2, len(big) - 1)}
    dropped = []
    for stale in ASSETS.glob("game_f*.png"):
        if stale.name not in keep:
            stale.unlink()
            dropped.append(stale.name)
    if dropped:
        print(f"removed   : {', '.join(sorted(dropped))} (no longer generated)")

    print(f"frames    : {len(big)} at {SCALE}x -> {W * SCALE}x{H * SCALE}")
    print(f"wrote     : {gif}  ({FRAME_MS}ms, loops)")
    print(f"wrote     : {strip}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
