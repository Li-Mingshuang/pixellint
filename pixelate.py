"""Turn any image into a verified pixel-art sprite, and give it procedural motion.

    python pixelate.py SOURCE.png --size 56x72 --palette game --out assets/hero
    python pixelate.py SOURCE.png --size 56x72 --animate --out assets/hero

WHAT THIS SOLVES, AND WHAT IT CANNOT.

It solves the deterministic half of the problem, which is most of it: downscale
with proper area averaging, snap every pixel to a locked palette in CIELAB, add a
silhouette outline, and then ASSERT the result (size, palette closure, one
connected body, colour separation, ground row). Every one of those is a fact, not
an opinion, and the pipeline already has the machinery.

It does NOT solve the half that made the last sprite ugly. There is no eyesight in
here. If the source is bad, the crop is wrong, or the subject is unrecognisable at
56x72, this will faithfully produce a verified, palette-clean, structurally perfect
piece of bad art. The source has to be chosen by someone who can see it.

ANIMATION IS PROCEDURAL, AND THAT IS A REAL LIMIT.

From ONE static image you can have motion that does not require new information:
a bob, a sway, a blink, a breath, a scroll. You cannot have a walk cycle, because
a walk cycle needs poses that are not in the picture. Anything claiming otherwise
is either morphing (which reads as melting) or using a generation model.

So `--animate` offers honest procedural motion and says so in the output.

LICENSING. Only feed this images you have the right to derive from -- your own, or
CC0 / public domain. Pixelating someone's art does not make it yours, and this repo
is public. See https://github.com/madjin/awesome-cc0 for a good starting list.
"""

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter

from gamepalette import GAME_PALETTE
from pixelkit import (SCENE_PALETTE, build, check_grid, preview,
                      report_separation, srgb_to_lab)

HERE = Path(__file__).resolve().parent
PALETTES = {"game": GAME_PALETTE, "scene": SCENE_PALETTE}


def parse_size(text: str) -> tuple[int, int]:
    w, h = text.lower().split("x")
    return int(w), int(h)


def quantise(img: Image.Image, palette, dither: bool) -> Image.Image:
    """Snap every opaque pixel to its nearest palette entry, in CIELAB.

    Nearest in RGB picks perceptually wrong colours constantly; nearest in Lab is
    the same amount of code and gets skin, foliage and metal right.
    """
    keys = [k for k in palette if k != "."]
    labs = [(k, srgb_to_lab(palette[k][:3])) for k in keys]
    px = img.load()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = px[x, y]
            if a < 128:
                px[x, y] = (0, 0, 0, 0)
                continue
            target = srgb_to_lab((r, g, b))
            best, best_d = keys[0], None
            for k, lab in labs:
                d = (lab[0] - target[0]) ** 2 + (lab[1] - target[1]) ** 2 \
                    + (lab[2] - target[2]) ** 2
                if best_d is None or d < best_d:
                    best, best_d = k, d
            px[x, y] = palette[best]
    return img


def outline(img: Image.Image, palette) -> Image.Image:
    """Put a K edge around the silhouette.

    This is what stops a downscaled photo from looking like a blurred thumbnail:
    pixel art reads because shapes have edges, and a 56x72 downscale has none.
    """
    w, h = img.size
    src = img.load()
    out = img.copy()
    dst = out.load()
    k = palette["K"]
    for y in range(h):
        for x in range(w):
            if src[x, y][3] == 0:
                continue
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if not (0 <= nx < w and 0 <= ny < h) or src[nx, ny][3] == 0:
                    dst[x, y] = k
                    break
    return out


def repair(grid: list[str], palette, max_passes: int = 12) -> tuple[list[str], int]:
    """Remap colours that create a hard separation failure.

    Naive quantisation is locally correct and globally wrong: each pixel goes to
    its nearest palette entry, which reliably produces two entries that are close
    to each other sitting side by side on a soft gradient. The pipeline notices --
    that is what it is for -- but a tool that emits work the pipeline rejects is
    not finished.

    So this walks the failing pairs and moves the RARER colour of each to the
    nearest palette entry that (a) resolves this pair and (b) does not start a new
    failure with the pixels it actually touches. Bounded, and it reports how many
    substitutions it made rather than silently massaging the image.
    """
    from pixelkit import adjacent_pairs, delta_e, verdict

    cells = [list(r) for r in grid]
    subs = 0
    keys = [k for k in palette if k != "."]

    def neighbours(y, x):
        for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= ny < len(cells) and 0 <= nx < len(cells[0]) and cells[ny][nx] != ".":
                yield cells[ny][nx]

    for _ in range(max_passes):
        fails = [p for p in adjacent_pairs([ "".join(r) for r in cells ], palette)
                 if verdict(p[0], p[1], palette)[0] == "fail"]
        if not fails:
            break
        progressed = False
        for a, b in fails:
            counts = {}
            total_a = sum(row.count(a) for row in cells)
            total_b = sum(row.count(b) for row in cells)
            move = a if total_a <= total_b else b
            stay = b if move == a else a
            # nearest alternatives first: the substitution should be as invisible
            # as the palette allows
            for cand in sorted((k for k in keys if k != move), key=lambda k: delta_e(k, move, palette)):
                if verdict(cand, stay, palette)[0] == "fail":
                    continue
                # does it introduce a NEW failure against anything it would touch?
                ok = True
                for y in range(len(cells)):
                    for x in range(len(cells[0])):
                        if cells[y][x] != move:
                            continue
                        for nb in neighbours(y, x):
                            if nb != move and verdict(cand, nb, palette)[0] == "fail":
                                ok = False
                                break
                        if not ok:
                            break
                    if not ok:
                        break
                if not ok:
                    continue
                for y in range(len(cells)):
                    for x in range(len(cells[0])):
                        if cells[y][x] == move:
                            cells[y][x] = cand
                subs += 1
                progressed = True
                break
        if not progressed:
            break
    return ["".join(r) for r in cells], subs


def keep_largest_body(img: Image.Image) -> Image.Image:
    """Drop everything not connected to the biggest opaque blob.

    Photos have background clutter, and after a hard alpha threshold some of it
    survives as specks. A sprite must be ONE connected body per the pipeline's
    own rule, so isolate it here rather than failing the check later.
    """
    w, h = img.size
    px = img.load()
    seen = [[False] * w for _ in range(h)]
    blobs = []
    for y in range(h):
        for x in range(w):
            if seen[y][x] or px[x, y][3] == 0:
                continue
            stack, cells = [(x, y)], []
            seen[y][x] = True
            while stack:
                cx, cy = stack.pop()
                cells.append((cx, cy))
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nx < w and 0 <= ny < h and not seen[ny][nx] \
                            and px[nx, ny][3] != 0:
                        seen[ny][nx] = True
                        stack.append((nx, ny))
            blobs.append(cells)
    if not blobs:
        return img
    keep = max(blobs, key=len)
    if len(keep) == sum(len(b) for b in blobs):
        return img
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dst = out.load()
    for x, y in keep:
        dst[x, y] = px[x, y]
    return out


def as_grid(img: Image.Image, palette) -> list[str]:
    inv = {v: k for k, v in palette.items()}
    return ["".join(inv[img.load()[x, y]] for x in range(img.width))
            for y in range(img.height)]


def animate(grid: list[str], frames: int = 4, bob: int = 1) -> list[list[str]]:
    """Procedural idle: the whole silhouette rises and falls by one pixel.

    Honest about its ceiling -- this is a breath, not a walk. It is also the only
    motion that a single image can support without inventing information.
    """
    out = []
    for i in range(frames):
        shift = bob if i in (1, 2) else 0
        rows = ["." * len(grid[0])] * shift + grid[:len(grid) - shift]
        out.append(rows)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="input image (yours, or CC0 / public domain)")
    ap.add_argument("--size", required=True, type=parse_size, help="native size, e.g. 56x72")
    ap.add_argument("--palette", choices=sorted(PALETTES), default="game")
    ap.add_argument("--out", required=True, help="output path stem, e.g. assets/hero")
    ap.add_argument("--no-outline", action="store_true")
    ap.add_argument("--no-repair", action="store_true",
                    help="skip the separation repair pass")
    ap.add_argument("--keep-specks", action="store_true")
    ap.add_argument("--alpha-threshold", type=int, default=128)
    ap.add_argument("--scale", type=int, default=6)
    ap.add_argument("--animate", action="store_true")
    ap.add_argument("--frames", type=int, default=4)
    ap.add_argument("--module", help="also write a pipeline module at this path")
    args = ap.parse_args()

    palette = PALETTES[args.palette]
    src = Image.open(args.source).convert("RGBA")

    # 1. area-average down to the native grid. BOX, not LANCZOS: for pixel art you
    #    want each output pixel to be the MEAN of the block it covers, because that
    #    is what makes the quantiser's job well-posed.
    small = src.resize(args.size, Image.Resampling.BOX)

    # 2. hard alpha, so the subject separates from its background
    a = small.getchannel("A").point(lambda v: 255 if v >= args.alpha_threshold else 0)
    small.putalpha(a)

    if not args.keep_specks:
        small = keep_largest_body(small)

    # 3. snap to the locked palette in Lab
    small = quantise(small, palette, dither=False)

    # 4. edge it
    if not args.no_outline:
        small = outline(small, palette)

    grid = as_grid(small, palette)

    subs = 0
    if not args.no_repair:
        grid, subs = repair(grid, palette)
        if subs:
            small = build(grid, palette)          # keep the saved assets in step
            if not args.no_outline:
                small = outline(small, palette)
            grid = as_grid(small, palette)

    out_stem = Path(args.out)
    out_stem.parent.mkdir(parents=True, exist_ok=True)
    native = out_stem.with_name(out_stem.name + "_native.png")
    small.save(native)
    preview(small, args.scale, palette["R"][:3]).save(
        out_stem.with_name(out_stem.name + "_preview.png"))

    # 5. verify, with the same assertions everything else in this repo uses
    problems = check_grid(grid, "pixelated", palette)
    failures, rows = report_separation(grid, "pixelated", palette=palette)
    keys = {c for row in grid for c in row if c != "."}
    lows = max((y for y in range(len(grid)) if any(c != "." for c in grid[y])), default=-1)

    print(f"source   : {args.source}  {src.size}")
    print(f"native   : {args.size[0]}x{args.size[1]}  ({args.size[0] * args.size[1]} cells)")
    print(f"palette  : {args.palette}, {len(keys)} of {len(palette) - 1} keys used")
    print(f"body     : {len(problems) and problems[0] or 'one connected body'}")
    print(f"ground   : lowest opaque row {lows} of {len(grid) - 1}")
    print(f"separation: {len(failures)} hard failure(s), {len(rows)} touching pairs"
          + (f", {subs} colour substitution(s) to get there" if subs else ""))

    if args.animate:
        frames = animate(grid, args.frames)
        imgs = [build(f, palette) for f in frames]
        gif = out_stem.with_name(out_stem.name + ".gif")
        pal = [preview(i, args.scale, palette["R"][:3]).convert("RGB").convert(
            "P", palette=Image.Palette.ADAPTIVE, colors=64) for i in imgs]
        pal[0].save(gif, save_all=True, append_images=pal[1:], duration=180,
                    loop=0, optimize=False)
        print(f"animation: {len(frames)} frames, single-pixel bob (NOT a walk cycle)")
        print(f"wrote    : {gif}")

    if args.module:
        mod = Path(args.module)
        lines = [
            f'"""Pixelated from {Path(args.source).name} by pixelate.py.',
            "",
            f"Native {args.size[0]}x{args.size[1]}. Palette: {args.palette}.",
            "Regenerate with:",
            f"    python pixelate.py {args.source} --size {args.size[0]}x{args.size[1]}"
            f" --palette {args.palette} --out {args.out}"
            + (" --animate" if args.animate else "")
            + f" --module {args.module}",
            '"""',
            "",
            f"from gamepalette import GAME_PALETTE",
            f"from pixelkit import SCENE_PALETTE",
            "",
            f'SHIPPED = ("SPRITE",)' + ('  # plus FRAMES when animated' if args.animate else ""),
            f"PALETTE = {'GAME_PALETTE' if args.palette == 'game' else 'SCENE_PALETTE'}",
            "",
            "SPRITE = [",
        ]
        lines += [f'    "{row}",' for row in grid]
        lines.append("]")
        if args.animate:
            lines += ["", "FRAMES = ["]
            for f in animate(grid, args.frames):
                lines.append("    [")
                lines += [f'        "{row}",' for row in f]
                lines.append("    ],")
            lines.append("]")
            lines[lines.index('SHIPPED = ("SPRITE",)  # plus FRAMES when animated')] = \
                'SHIPPED = ("SPRITE", "FRAMES")'
        lines.append("")
        mod.parent.mkdir(parents=True, exist_ok=True)
        mod.write_text("\n".join(lines), encoding="utf-8")
        print(f"wrote    : {mod}")

    print(f"wrote    : {native}")
    print(f"wrote    : {out_stem.with_name(out_stem.name + '_preview.png')}")

    if problems or failures:
        print("\nNOT CLEAN. The pipeline assertions found real problems; adjust the"
              " crop, the size, or the palette choice, and run again.")
        return 1
    print("\nClean: palette-closed, one body, every touching pair readable.")
    print("NOTE: that says nothing about whether it LOOKS good. Only you can see it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
