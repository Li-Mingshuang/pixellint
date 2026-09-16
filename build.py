"""Build every asset and then run the full verification suite.

    python build.py

Exits non-zero if any check fails, which is what the CI workflow relies on.

Render steps run first, in dependency order. Checks are then discovered by glob
(`check_*.py`) so a layer added later brings its own assertions along without
anyone having to remember to register them here.
"""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

RENDER_STEPS = [
    ("render idle sprite", "render_sprite.py"),
    ("render walk cycle", "walk_cycle.py"),
    ("render sky layer", "render_sky.py"),
    ("compose scene", "scene.py"),
]

# Checks run in this order; anything else matching check_*.py is appended and
# run alphabetically.
CHECK_ORDER = ["check_sprite.py", "check_scene.py"]


def run(script: Path) -> int:
    return subprocess.call([sys.executable, str(script)], cwd=HERE)


def main() -> int:
    for label, script in RENDER_STEPS:
        print(f"\n=== {label}: {script} " + "=" * max(0, 46 - len(label) - len(script)))
        rc = run(HERE / script)
        if rc != 0:
            print(f"\nFAILED at render step '{label}' (exit {rc})")
            return rc

    discovered = sorted(p.name for p in HERE.glob("check_*.py"))
    checks = [c for c in CHECK_ORDER if c in discovered]
    checks += [c for c in discovered if c not in checks and c != "check_scene.py"]

    failed = []
    for script in checks:
        print(f"\n=== verify: {script} " + "=" * max(0, 46 - len(script)))
        if run(HERE / script) != 0:
            failed.append(script)

    print("\n" + "=" * 60)
    print(f"render steps : {len(RENDER_STEPS)} ok")
    print(f"checks run   : {len(checks)}")
    if failed:
        print(f"FAILED       : {', '.join(failed)}")
        return 1
    print("All steps passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
