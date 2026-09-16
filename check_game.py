"""Run the game's headless playability test, so `build.py` covers it too.

The real test lives in `game/smoke_test.mjs` (Node stubs the DOM and drives the
actual script out of index.html). This wrapper exists only so the Python build
discovers it alongside every other `check_*.py`.
"""

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("  SKIP  node not found; game playability not checked")
        return 0
    test = HERE / "game" / "smoke_test.mjs"
    if not test.exists():
        print(f"  FAIL  missing {test}")
        return 1
    rc = subprocess.call([node, str(test)], cwd=HERE)
    if rc != 0:
        print("  FAIL  game playability")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
