"""Build every asset, then run the full verification suite.

    python build.py                 # incremental, parallel
    python build.py --force         # ignore the cache, rebuild everything
    python build.py --jobs 1        # serial, for readable interleaved output

Two things make this fast, and measurement said they were the right two. The
profile was:

    total 13.8 s
      render  8.1 s   (compose scene 3.08 s + game gif 2.31 s = two thirds of it)
      checks  5.8 s   (game/check_background 1.19 s was the heaviest single check)
      interpreter startup: 30 processes x 67 ms = 2.0 s

Startup was NOT the cost, so this does not try to save it. What it does instead:

  PARALLEL. The steps inside a wave have no dependencies on each other, so they
  run concurrently and each wave is bounded by its slowest member rather than by
  the sum.

  INCREMENTAL. A step is skipped when every output it declares already exists and
  is newer than every .py in the tree. That makes a no-op rebuild nearly free,
  which is the common case when you re-run the build just to re-check something.
  The rule is deliberately coarse -- any source change rebuilds everything -- so
  it can never be wrong, only slower than it could be.

Steps are grouped into waves by real dependency, not by convenience: the game GIF
reads `game/assets.js`, which the atlas packer writes, so it cannot run beside it.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent

# (label, script, [output globs]). Outputs are declared so the incremental check
# has something real to test; a step that declares nothing is always run.
WAVE_1 = [
    ("render idle sprite", "render_sprite.py", ["assets/char_*.png"]),
    ("render walk cycle", "walk_cycle.py", ["assets/walk_*.png", "assets/walk.gif"]),
    ("render sky layer", "render_sky.py", ["assets/sky_*.png"]),
    ("render dog layer", "dog.py", ["assets/dog_*.png", "assets/dog.gif"]),
    ("render mechpup", "mechdog.py", ["assets/mechdog_*.png", "assets/mechdog.gif"]),
    ("render pilotpup", "mech.py", ["assets/mech_*.png", "assets/mech.gif"]),
    ("compose scene", "scene.py", ["assets/meadow_*.png", "assets/meadow.gif"]),
    ("render game player", "game/player.py", ["assets/player_*.png", "assets/player_*.gif"]),
    ("render game zombie", "game/zombie.py", ["assets/zombie_*.png", "assets/zombie_*.gif"]),
    ("render game effects", "game/effects.py", ["assets/fx_*.png", "assets/fx_*.gif"]),
    ("pack game atlas", "export_game_atlas.py", ["game/assets.js", "assets/game_atlas.png"]),
]
# the gameplay GIF replays the atlas, so it has to follow the packer
WAVE_2 = [
    ("render game gif", "render_game_gif.py", ["assets/game.gif", "assets/game_strip.png"]),
]
REPORT_STEPS = [
    ("evaluate", ["evaluate.py", "--markdown", "--json"]),
]

# Checks run first in this order, then anything else matching check_*.py.
CHECK_ORDER = ["check_sprite.py", "check_scene.py", "check_mech.py"]

RUN_LOG = HERE / ".pipeline-runs.jsonl"


def record(script: str, ok: bool) -> None:
    try:
        with RUN_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"script": script, "ok": bool(ok),
                                 "ts": round(time.time(), 1)}) + "\n")
    except Exception:
        pass          # logging must never break the build


def step_inputs(script: str) -> set[Path]:
    """The local modules a step transitively imports, found by parsing, not by list.

    A hand-written dependency list is the thing that keeps going stale in this
    repo, and a stale dependency in a build cache is worse than no cache: it
    silently serves old outputs as if they were new. So the graph is DERIVED --
    each script's imports are parsed with `ast`, resolved to local `.py` files, and
    followed transitively.

    Data files a step reads cannot be found that way, so a step may declare extras
    (the scene spec is the only one).
    """
    import ast

    seen, stack = set(), [HERE / script]
    while stack:
        p = stack.pop()
        if p in seen or not p.exists():
            continue
        seen.add(p)
        for n in _imports_of(p):
            for cand in (HERE / f"{n}.py", HERE / "game" / f"{n}.py"):
                if cand.exists():
                    stack.append(cand)

    for pattern in EXTRA_INPUTS.get(script, []):
        seen.update(HERE.glob(pattern))
    return seen


_IMPORT_CACHE: dict = {}


def _imports_of(path: Path) -> list:
    """Top-level module names a file imports, cached against its mtime.

    Parsing is the expensive half of the freshness test and the same modules are
    reached from a dozen different steps, so without this the build re-parses
    `pixelkit.py` once per step. Keying the cache on mtime rather than just the
    path is what keeps it honest: an edited file gets a new mtime and is re-parsed,
    so a stale cache entry cannot make a step look fresh when it is not.
    """
    import ast

    try:
        stamp = path.stat().st_mtime_ns
    except OSError:
        return []
    key = (str(path), stamp)
    hit = _IMPORT_CACHE.get(key)
    if hit is not None:
        return hit
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        _IMPORT_CACHE[key] = []
        return []
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module.split(".")[0])
    _IMPORT_CACHE[key] = names
    return names


# Data files a step reads, which import parsing cannot reveal.
EXTRA_INPUTS = {
    "scene.py": ["scenes/*.json"],
}


def is_fresh(script: str, outputs) -> bool:
    """True when every declared output exists and postdates this step's inputs."""
    if not outputs:
        return False
    inputs = step_inputs(script)
    if not inputs:
        return False
    newest = max(p.stat().st_mtime for p in inputs)
    seen = False
    for pattern in outputs:
        hits = list(HERE.glob(pattern))
        if not hits:
            return False
        seen = True
        if min(p.stat().st_mtime for p in hits) < newest:
            return False
    return seen


def run_step(label: str, script: str, outputs, jobs: int, force: bool):
    if not force and is_fresh(script, outputs):
        return label, script, 0, 0.0, "cached"
    t0 = time.perf_counter()
    proc = subprocess.run([sys.executable, str(HERE / script)], cwd=HERE,
                          capture_output=True, text=True)
    dt = time.perf_counter() - t0
    if proc.returncode != 0:
        sys.stdout.write(proc.stdout)
        sys.stderr.write(proc.stderr)
    return label, script, proc.returncode, dt, "ran"


def run_wave(steps, jobs: int, force: bool, heading: str):
    """Run a wave concurrently; print each step's result in declaration order."""
    if not steps:
        return []
    results = [None] * len(steps)
    with ThreadPoolExecutor(max_workers=max(1, min(jobs, len(steps)))) as pool:
        futures = [pool.submit(run_step, *s, jobs, force) for s in steps]
        for i, fut in enumerate(futures):
            results[i] = fut.result()

    print(f"\n=== {heading} " + "=" * max(0, 60 - len(heading)))
    for label, script, rc, dt, how in results:
        tag = "cached" if how == "cached" else ("ok" if rc == 0 else f"FAIL rc={rc}")
        print(f"  {label:<22} {dt*1000:>7.0f} ms  {tag}")
    return results


def check_scripts():
    discovered = sorted(p.relative_to(HERE).as_posix() for p in HERE.rglob("check_*.py"))
    ordered = [c for c in CHECK_ORDER if c in discovered]
    ordered += [c for c in discovered if c not in ordered]
    return ordered


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="ignore the incremental cache")
    ap.add_argument("--jobs", type=int, default=0,
                    help="parallel workers (0 = one per CPU)")
    args = ap.parse_args()
    jobs = args.jobs or (os.cpu_count() or 4)

    # Steps that stream (the report steps) inherit this process's stdout and write
    # straight to the file descriptor, while this process buffers its own prints in
    # userspace. Piped into a file or a pager -- which is how CI, and every timing
    # run, reads this log -- that put the entire evaluate report AHEAD of the build
    # log it belongs to, so the timings appeared to come after the thing they
    # measured. Line buffering makes the parent flush per line and the order hold.
    sys.stdout.reconfigure(line_buffering=True)

    t_start = time.perf_counter()
    print(f"build: {jobs} workers, incremental={'off' if args.force else 'on'}")

    failed = []

    run_wave(WAVE_1, jobs, args.force, "render")
    run_wave(WAVE_2, jobs, args.force, "render (dependent)")

    scripts = check_scripts()
    # Checks are read-only with respect to each other, so one wave is safe. They
    # ALWAYS run: `force=True` here, because a check is cheap next to the cost of
    # not having run it.
    results = run_wave([(s, s, []) for s in scripts], jobs, True, "verify")
    for label, script, rc, dt, how in results:
        record(script, rc == 0)
        if rc != 0:
            failed.append(script)

    if failed:
        print(f"\nFAILED: {', '.join(failed)}")
        return 1

    for label, argv in REPORT_STEPS:
        print(f"\n=== report: {label} " + "=" * max(0, 46 - len(label)))
        subprocess.call([sys.executable, *argv], cwd=HERE)

    record("__build__", True)
    print(f"\nAll steps passed in {time.perf_counter() - t_start:.1f}s.")
    print("(pass --force to rebuild everything, --jobs 1 for serial output)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
