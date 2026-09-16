"""Spec-driven pixel-art scene compositor.

A scene is a JSON spec plus a set of grid modules. The pipeline is:

    spec (scenes/*.json)
        -> resolve each layer's grid from its module
        -> composite onto the canvas at the character-grid level
        -> render PNG frames + a looping GIF
        -> assert (check_scene.py)

Compositing at the character-grid level matters: the finished frame is itself a
grid, so the same structural and palette assertions that police a single sprite
run over the whole 160x96 scene.

Seamless loops are a design constraint, not a hope. Every animated element must
return to its exact starting state after `loop_frames`:

    a 4-frame walk        16/4 = 4 cycles        -> exact
    a 4-frame trot        16/4 = 4 cycles        -> exact
    clouds at 4px/frame   16*4 = 64px = 1 tile   -> exact
    4 smoke puffs         each fades before wrap -> exact

check_scene.py proves it by composing frame `loop_frames` and asserting it is
pixel-identical to frame 0.

    python scene.py                     # build scenes/meadow.json
    python scene.py scenes/other.json   # build a different scene
"""

import json
import sys
from pathlib import Path

from PIL import Image

from pixelkit import SCENE_PALETTE, build, preview

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "assets"
OUT_DIR.mkdir(parents=True, exist_ok=True)
BG = (24, 26, 34)


def load_spec(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def resolve(module_name: str, attr: str, cache: dict):
    """Import a grid module lazily and pull one attribute out of it."""
    if module_name not in cache:
        try:
            cache[module_name] = __import__(module_name)
        except ImportError as exc:
            cache[module_name] = exc
    mod = cache[module_name]
    if isinstance(mod, Exception):
        return None, f"module '{module_name}' unavailable: {mod}"
    if not hasattr(mod, attr):
        return None, f"module '{module_name}' has no attribute '{attr}'"
    return getattr(mod, attr), None


# --------------------------------------------------------------------------
# Grid drawing primitives. Everything works on list-of-list-of-char.
# --------------------------------------------------------------------------
def blank(w: int, h: int):
    return [["." for _ in range(w)] for _ in range(h)]


def blit(canvas, grid, x, y, w, h):
    for r, row in enumerate(grid):
        sy = y + r
        if not (0 <= sy < h):
            continue
        crow = canvas[sy]
        for c, ch in enumerate(row):
            if ch == ".":
                continue
            sx = x + c
            if 0 <= sx < w:
                crow[sx] = ch


def lowest_opaque_row(grid) -> int:
    for r in range(len(grid) - 1, -1, -1):
        if any(ch != "." for ch in grid[r]):
            return r
    return len(grid) - 1


def draw_layer(canvas, grid, layer, w, h):
    if layer.get("base") is not None:
        y = layer["base"] - lowest_opaque_row(grid)
    else:
        y = layer.get("y", 0)
    x = layer.get("x", 0)

    if layer.get("tile_horizontal"):
        tile_w = len(grid[0])
        # fixed layers that tile simply repeat, scrolled ones are handled by
        # the caller passing an already-scrolled offset through layer['_x']
        x = layer.get("_x", x)
        while x < w:
            blit(canvas, grid, x, y, w, h)
            x += tile_w
    else:
        blit(canvas, grid, x, y, w, h)


# --------------------------------------------------------------------------
# Effects
# --------------------------------------------------------------------------
def smoke_puffs(fx, frame, loop_frames):
    puffs = fx.get("puffs", 4)
    fade = fx.get("fade_after", 13)
    top, base_x = fx.get("top", 40), fx.get("x", 0)
    out = []
    for p in range(puffs):
        age = (frame - p * (loop_frames // puffs)) % loop_frames
        if age >= fade:
            continue
        size = 1 + age // 5
        shade = "W" if age < 7 else "w"
        x = base_x + (1 if (age // 4) % 2 else 0) + (p % 2)
        y = top - age
        grid = [
            "".join("." if (abs(dx) + abs(dy)) > size else shade
                    for dx in range(-size, size + 1))
            for dy in range(-size, size + 1)
        ]
        out.append((x - size, y - size, grid))
    return out


# --------------------------------------------------------------------------
# Composition
# --------------------------------------------------------------------------
class Scene:
    def __init__(self, spec: dict):
        self.spec = spec
        self.w, self.h = spec["size"]
        self.loop_frames = spec["loop_frames"]
        self.cache: dict = {}
        self.layers = []
        self.missing = []
        for layer in spec["layers"]:
            grid, err = resolve(layer["module"], layer["attr"], self.cache)
            if err:
                self.missing.append(f"{layer['name']}: {err}")
                continue
            self.layers.append((layer, grid))

    def compose(self, frame: int):
        w, h = self.w, self.h
        canvas = blank(w, h)

        for layer, grid in self.layers:
            if layer.get("animated"):
                frames = grid
                grid = frames[(frame + layer.get("phase", 0)) % len(frames)]

            if layer.get("scroll_px_per_frame"):
                scroll = (frame * layer["scroll_px_per_frame"]) % len(grid[0])
                layer = {**layer, "_x": -scroll}

            draw_layer(canvas, grid, layer, w, h)

        for fx in self.spec.get("effects", []):
            if fx.get("type") == "smoke":
                for x, y, puff in smoke_puffs(fx, frame, self.loop_frames):
                    blit(canvas, puff, x, y, w, h)

        return ["".join(r) for r in canvas]


def main(argv: list[str]) -> int:
    spec_path = Path(argv[1]) if len(argv) > 1 else HERE / "scenes" / "meadow.json"
    spec = load_spec(spec_path)
    print(f"scene     : {spec['name']}  ({spec.get('description', '')})")
    print(f"spec      : {spec_path}")

    sc = Scene(spec)
    for m in sc.missing:
        print(f"  ! {m}")
    print(f"layers    : {len(sc.layers)} resolved, {len(sc.missing)} missing")

    scale = spec.get("gif_scale", 4)
    grids = [sc.compose(f) for f in range(sc.loop_frames)]
    images = [build(g) for g in grids]

    for f, g in enumerate(grids):
        build(g).save(OUT_DIR / f"{spec['name']}_f{f:02d}.png")

    # contact strip of the first four frames
    pad = 4
    strip = Image.new("RGBA", (4 * scale * sc.w + 5 * pad, scale * sc.h + 2 * pad), BG)
    for i in range(min(4, len(images))):
        strip.alpha_composite(preview(images[i], scale, BG),
                              (pad + i * (scale * sc.w + pad), pad))
    strip.save(OUT_DIR / f"{spec['name']}_strip.png")

    for mult, suffix in ((1, ""), (2, "_large")):
        gif = [
            preview(img, scale * mult, BG).convert("RGB").convert(
                "P", palette=Image.Palette.ADAPTIVE, colors=128)
            for img in images
        ]
        name = f"{spec['name']}{suffix}.gif"
        gif[0].save(OUT_DIR / name, save_all=True, append_images=gif[1:],
                    duration=spec["frame_ms"], loop=0, optimize=False)
        print(f"wrote     : {OUT_DIR / name}  "
              f"({sc.w * scale * mult}x{sc.h * scale * mult}, {len(gif)} frames, "
              f"{spec['frame_ms']}ms)")

    print(f"wrote     : {OUT_DIR / (spec['name'] + '_strip.png')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
