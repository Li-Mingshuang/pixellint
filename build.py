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
    ("render dog layer", "dog.py"),
    ("compose scene", "scene.py"),
    ("render game player", "game/player.py"),
    ("render game zombie", "game/zombie.py"),
    ("render game effects", "game/effects.py"),
    ("pack game atlas", "export_game_atlas.py"),
    ("render game gif", "render_game_gif.py"),
]

# Checks run in this order; anything else matching check_*.py is appended and
# run alphabetically.
CHECK_ORDER = ["check_sprite.py", "check_scene.py"]

# Reporting steps run last and are allowed to return non-zero: they measure, they
# do not gate. evaluate.py exits non-zero when an asset is unclean, which the
# check scripts have already decided on -- failing the build again here would
# just double-report.
REPORT_STEPS = [
    ("evaluate", ["evaluate.py", "--markdown", "--json"]),
]


def run(script: Path) -> int:
    return subprocess.call([sys.executable, str(script)], cwd=HERE)


def main() -> int:
    for label, script in RENDER_STEPS:
        print(f"\n=== {label}: {script} " + "=" * max(0, 46 - len(label) - len(script)))
        rc = run(HERE / script)
        if rc != 0:
            print(f"\nFAILED at render step '{label}' (exit {rc})")
            return rc

    # Checks are discovered RECURSIVELY. A non-recursive glob silently skips
    # game/check_*.py, which is exactly the kind of "the suite is green because
    # half of it never ran" failure this project is supposed to be about.
    discovered = sorted(p.relative_to(HERE).as_posix() for p in HERE.rglob("check_*.py"))
    checks = [c for c in CHECK_ORDER if c in discovered]
    checks += [c for c in discovered if c not in checks]

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

    for label, argv in REPORT_STEPS:
        print(f"\n=== report: {label} " + "=" * max(0, 46 - len(label)))
        subprocess.call([sys.executable, *argv], cwd=HERE)

    print("\nAll steps passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
