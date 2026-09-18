"""Prove the committed assets are reproducible from the source grids.

Byte comparison is NOT a valid check here. PNG bytes legitimately differ between
platforms and Pillow/zlib builds even when the image content is identical (the
first version of this CI check asserted byte equality and failed on Linux while
the build itself passed). What must actually hold is that regenerating from the
grids reproduces the same *pixels*, frame for frame.

So: snapshot the decoded pixels of every committed asset, run the build, then
compare the decoded pixels again.
"""

import io
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageSequence

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"


def digest(path: Path):
    """Decode an asset into a comparable, format-independent summary."""
    img = Image.open(path)
    if getattr(img, "n_frames", 1) > 1:
        frames = [f.convert("RGB").tobytes() for f in ImageSequence.Iterator(img)]
        return ("anim", img.size, img.info.get("duration"), img.info.get("loop"), tuple(frames))
    return ("still", img.size, img.convert("RGBA").tobytes())


def snapshot() -> dict[str, object]:
    return {p.name: digest(p) for p in sorted(ASSETS.glob("*")) if p.is_file()}


def main() -> int:
    if not ASSETS.is_dir():
        print(f"no assets directory at {ASSETS}")
        return 1

    before = snapshot()
    if not before:
        print("assets directory is empty - nothing to compare")
        return 1

    print(f"snapshotted {len(before)} committed asset(s)")
    print("regenerating (forced: an incremental build would skip the very steps"
          " this check exists to verify)...")
    rc = subprocess.call([sys.executable, str(HERE / "build.py"), "--force"], cwd=HERE)
    if rc != 0:
        print(f"build failed (exit {rc})")
        return rc

    after = snapshot()

    print("\n-- pixel-level reproducibility ------------------------------")
    problems = []

    for name in sorted(set(before) | set(after)):
        if name not in before:
            problems.append(f"{name}: appeared after regeneration but is not committed")
            print(f"  FAIL  {name}  (untracked output)")
        elif name not in after:
            problems.append(f"{name}: committed but no longer generated")
            print(f"  FAIL  {name}  (missing after build)")
        elif before[name] != after[name]:
            problems.append(f"{name}: decoded pixels changed")
            print(f"  FAIL  {name}  (pixels differ)")
        else:
            kind = before[name][0]
            extra = ""
            if kind == "anim":
                _, size, dur, loop, frames = before[name]
                extra = f"  {len(frames)} frames, {dur}ms, loop={loop}"
            else:
                extra = f"  {before[name][1][0]}x{before[name][1][1]}"
            print(f"  ok    {name}{extra}")

    print()
    if problems:
        print(f"reproducibility failures: {len(problems)}")
        for p in problems:
            print(f"  - {p}")
        return 1

    print("ok - every committed asset is byte-independent but pixel-identical "
          "when regenerated from the grids")
    return 0


if __name__ == "__main__":
    sys.exit(main())
