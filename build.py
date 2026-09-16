"""Build every asset and then run the full verification suite.

    python build.py

Exits non-zero if any check fails, which is what the CI workflow relies on.
"""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

STEPS = [
    ("render idle sprite", "render_sprite.py"),
    ("render walk cycle", "walk_cycle.py"),
    ("verify", "check_sprite.py"),
]


def main() -> int:
    for label, script in STEPS:
        print(f"\n=== {label}: {script} " + "=" * (46 - len(label) - len(script)))
        rc = subprocess.call([sys.executable, str(HERE / script)], cwd=HERE)
        if rc != 0:
            print(f"\nFAILED at step '{label}' (exit {rc})")
            return rc
    print("\nAll steps passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
